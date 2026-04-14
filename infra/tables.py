from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb


class QuizTables(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.quizzes = dynamodb.Table(
            self, "Quizzes",
            partition_key=dynamodb.Attribute(name="quiz_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.responses = dynamodb.Table(
            self, "Responses",
            partition_key=dynamodb.Attribute(name="quiz_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.leaderboard = dynamodb.Table(
            self, "Leaderboard",
            partition_key=dynamodb.Attribute(name="period", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        self.leaderboard.add_local_secondary_index(
            index_name="by_score",
            sort_key=dynamodb.Attribute(name="score", type=dynamodb.AttributeType.NUMBER),
        )

        self.config = dynamodb.Table(
            self, "Config",
            partition_key=dynamodb.Attribute(name="config_key", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
