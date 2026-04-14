# Contributing

## Development Setup

```bash
git clone <repo-url>
cd quizrepo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Project Structure

```
├── app.py                  # CDK app entry point
├── infra/
│   ├── stack.py            # CDK stack — all AWS resources
│   └── tables.py           # DynamoDB table constructs
├── shared/
│   └── models.py           # Pydantic data models (shared across Lambdas)
├── lambdas/
│   ├── quiz_generator/     # Bedrock quiz generation
│   ├── answer_collector/   # Answer storage (shared logic)
│   ├── slack_bot/          # Slack Block Kit integration
│   ├── teams_bot/          # Teams Adaptive Cards integration
│   ├── scorer/             # Scoring engine + leaderboard
│   ├── results_publisher/  # Results publishing to channels
│   └── admin/              # Admin slash commands
├── tests/
└── docs/
```

## Coding Conventions

- Python 3.9+ compatible
- Use type hints where practical
- Data models go in `shared/models.py` using Pydantic
- Each Lambda is a self-contained directory under `lambdas/` with a `handler.py`
- Lambda handlers export a `handler(event, context)` function
- Environment variables for configuration — no hardcoded values
- DynamoDB operations use `boto3.resource("dynamodb")` for cleaner API

## Adding a New Lambda

1. Create `lambdas/<name>/handler.py` with a `handler(event, context)` function
2. Create `lambdas/<name>/__init__.py`
3. Add the Lambda function to `infra/stack.py` with appropriate IAM permissions
4. Wire it to API Gateway / EventBridge as needed
5. Add CDK outputs for any new URLs

## Running Tests

```bash
pytest
```

## CDK Commands

```bash
npx cdk synth     # Generate CloudFormation template
npx cdk diff      # Preview changes
npx cdk deploy    # Deploy to AWS
npx cdk destroy   # Tear down all resources
```

## Making Changes

1. Create a feature branch from `main`
2. Make your changes
3. Run `npx cdk synth` to verify the stack compiles
4. Run `pytest` to verify tests pass
5. Open a pull request with a description of the change
