from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_apigateway as apigw
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_secretsmanager as sm
import aws_cdk.aws_iam as iam
from infra.tables import QuizTables

RUNTIME = _lambda.Runtime.PYTHON_3_12


class QuizSystemStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- DynamoDB Tables ---
        self.tables = QuizTables(self, "Tables")

        # --- Secrets ---
        secrets = sm.Secret(self, "QuizSecrets", secret_name="quiz-system/secrets")

        # --- Shared Lambda layer for common deps ---
        shared_env = {
            "QUIZZES_TABLE": self.tables.quizzes.table_name,
            "RESPONSES_TABLE": self.tables.responses.table_name,
            "LEADERBOARD_TABLE": self.tables.leaderboard.table_name,
            "CONFIG_TABLE": self.tables.config.table_name,
        }

        # --- Quiz Generator Lambda ---
        quiz_generator = _lambda.Function(
            self, "QuizGenerator",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/quiz_generator"),
            timeout=cdk.Duration.seconds(60),
            memory_size=256,
            environment={**shared_env, "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0"},
        )
        self.tables.quizzes.grant_read_write_data(quiz_generator)
        self.tables.config.grant_read_data(quiz_generator)
        quiz_generator.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"], resources=["*"],
        ))

        # --- Answer Collector Lambda ---
        answer_collector = _lambda.Function(
            self, "AnswerCollector",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/answer_collector"),
            timeout=cdk.Duration.seconds(10),
            environment=shared_env,
        )
        self.tables.responses.grant_read_write_data(answer_collector)
        self.tables.quizzes.grant_read_data(answer_collector)

        # --- Results Publisher Lambda ---
        results_publisher = _lambda.Function(
            self, "ResultsPublisher",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/results_publisher"),
            timeout=cdk.Duration.seconds(30),
            environment={
                **shared_env,
                "SLACK_BOT_TOKEN": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:SLACK_BOT_TOKEN}}",
                "SLACK_CHANNEL": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:SLACK_CHANNEL}}",
                "TEAMS_WEBHOOK_URL": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:TEAMS_WEBHOOK_URL}}",
            },
        )
        self.tables.leaderboard.grant_read_data(results_publisher)
        secrets.grant_read(results_publisher)

        # --- Scorer Lambda ---
        scorer = _lambda.Function(
            self, "Scorer",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/scorer"),
            timeout=cdk.Duration.seconds(60),
            environment={**shared_env, "RESULTS_PUBLISHER_ARN": results_publisher.function_arn},
        )
        self.tables.quizzes.grant_read_write_data(scorer)
        self.tables.responses.grant_read_data(scorer)
        self.tables.leaderboard.grant_read_write_data(scorer)
        results_publisher.grant_invoke(scorer)

        # --- Slack Bot Lambda ---
        slack_bot = _lambda.Function(
            self, "SlackBot",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/slack_bot"),
            timeout=cdk.Duration.seconds(10),
            environment={
                **shared_env,
                "SLACK_BOT_TOKEN": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:SLACK_BOT_TOKEN}}",
                "SLACK_SIGNING_SECRET": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:SLACK_SIGNING_SECRET}}",
                "SLACK_CHANNEL": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:SLACK_CHANNEL}}",
            },
        )
        self.tables.quizzes.grant_read_data(slack_bot)
        self.tables.responses.grant_read_write_data(slack_bot)
        secrets.grant_read(slack_bot)

        # --- Teams Bot Lambda ---
        teams_bot = _lambda.Function(
            self, "TeamsBot",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/teams_bot"),
            timeout=cdk.Duration.seconds(10),
            environment={
                **shared_env,
                "TEAMS_WEBHOOK_URL": "{{resolve:secretsmanager:quiz-system/secrets:SecretString:TEAMS_WEBHOOK_URL}}",
            },
        )
        self.tables.quizzes.grant_read_data(teams_bot)
        self.tables.responses.grant_read_write_data(teams_bot)
        secrets.grant_read(teams_bot)

        # --- Admin Lambda ---
        admin = _lambda.Function(
            self, "Admin",
            runtime=RUNTIME,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambdas/admin"),
            timeout=cdk.Duration.seconds(10),
            environment={**shared_env, "QUIZ_GENERATOR_ARN": quiz_generator.function_arn},
        )
        self.tables.config.grant_read_write_data(admin)
        quiz_generator.grant_invoke(admin)

        # --- API Gateway ---
        api = apigw.RestApi(self, "QuizApi", rest_api_name="Quiz System API")

        slack_resource = api.root.add_resource("slack")
        slack_resource.add_resource("events").add_method("POST", apigw.LambdaIntegration(slack_bot))
        slack_resource.add_resource("interactions").add_method("POST", apigw.LambdaIntegration(slack_bot))

        teams_resource = api.root.add_resource("teams")
        teams_resource.add_resource("messages").add_method("POST", apigw.LambdaIntegration(teams_bot))

        api.root.add_resource("answers").add_method("POST", apigw.LambdaIntegration(answer_collector))
        api.root.add_resource("admin").add_method("POST", apigw.LambdaIntegration(admin))

        # --- EventBridge: Quiz generation schedule (weekdays 10 AM UTC) ---
        events.Rule(
            self, "QuizSchedule",
            schedule=events.Schedule.cron(minute="0", hour="10", week_day="MON-FRI"),
            targets=[targets.LambdaFunction(quiz_generator)],
        )

        # --- EventBridge: Scorer runs every 15 min to check for closed quizzes ---
        events.Rule(
            self, "ScorerSchedule",
            schedule=events.Schedule.rate(cdk.Duration.minutes(15)),
            targets=[targets.LambdaFunction(scorer)],
        )

        # --- Outputs ---
        cdk.CfnOutput(self, "ApiUrl", value=api.url)
        cdk.CfnOutput(self, "SlackEventsUrl", value=f"{api.url}slack/events")
        cdk.CfnOutput(self, "SlackInteractionsUrl", value=f"{api.url}slack/interactions")
        cdk.CfnOutput(self, "TeamsMessagesUrl", value=f"{api.url}teams/messages")
        cdk.CfnOutput(self, "AdminUrl", value=f"{api.url}admin")
