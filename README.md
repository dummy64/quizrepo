# AI Quiz System

Fully automated, AI-powered daily quiz system for Entain India. Generates quizzes using AWS Bedrock (Claude), distributes them via Slack and Microsoft Teams, collects time-boxed answers, scores them, and publishes daily results + a running leaderboard — all with minimal human intervention.

## Features

- **AI-generated quizzes** — Configurable topics (general knowledge, tech trivia, or custom themes)
- **Dual platform** — Slack (Block Kit) and Microsoft Teams (Adaptive Cards)
- **Zero signup** — Uses Slack/Teams user identity directly
- **Time-boxed** — Configurable answer window with automatic closure
- **Leaderboard** — Daily results + all-time cumulative rankings
- **Admin controls** — `/quiz` slash commands for on-demand triggers and config changes
- **Fully serverless** — AWS Lambda, DynamoDB, EventBridge, API Gateway via CDK

## Architecture

```
EventBridge (cron) ──► Quiz Generator Lambda ──► Bedrock Claude
                              │
                              ├──► DynamoDB (Quizzes)
                              ├──► Slack Bot Lambda ──► Slack Channel
                              └──► Teams Bot Lambda ──► Teams Channel
                                        │
                                   User answers
                                        │
                              Answer Collector Lambda ──► DynamoDB (Responses)
                                        │
EventBridge (15 min) ──► Scorer Lambda ──► DynamoDB (Leaderboard)
                              │
                       Results Publisher ──► Slack + Teams
```

See [docs/architecture.md](docs/architecture.md) for detailed data flow.

## Project Structure

```
├── app.py                           # CDK app entry point
├── cdk.json                         # CDK configuration
├── pyproject.toml                   # Python dependencies
├── infra/
│   ├── stack.py                     # CDK stack (Lambdas, API GW, EventBridge, IAM)
│   └── tables.py                    # DynamoDB table constructs
├── shared/
│   └── models.py                    # Pydantic data models
├── lambdas/
│   ├── quiz_generator/handler.py    # Bedrock quiz generation
│   ├── answer_collector/handler.py  # Answer storage with dedup/expiry
│   ├── slack_bot/handler.py         # Slack Block Kit integration
│   ├── teams_bot/handler.py         # Teams Adaptive Cards integration
│   ├── scorer/handler.py            # Scoring engine + leaderboard
│   ├── results_publisher/handler.py # Results publishing
│   └── admin/handler.py             # Admin slash commands
├── tests/
└── docs/
```

## Quick Start

### Prerequisites

- Python 3.9+
- AWS CLI configured with appropriate credentials
- Node.js (for CDK CLI)
- A Slack workspace with admin access
- A Microsoft Teams channel with webhook permissions

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure Secrets

Create a secret in AWS Secrets Manager named `quiz-system/secrets` with these keys:

| Key | Description |
|-----|-------------|
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Slack app signing secret |
| `SLACK_CHANNEL` | Slack channel ID to post quizzes |
| `TEAMS_WEBHOOK_URL` | Teams incoming webhook URL |

### Deploy

```bash
npx cdk bootstrap   # first time only
npx cdk deploy
```

After deployment, CDK outputs the API Gateway URLs. Configure these in your Slack app and Teams bot settings. See [docs/deployment.md](docs/deployment.md) for the full step-by-step guide.

## Admin Commands

Use the `/quiz` slash command in Slack:

| Command | Description |
|---------|-------------|
| `/quiz now` | Trigger a quiz immediately |
| `/quiz config topic <theme>` | Set quiz topic/theme |
| `/quiz config num_questions <n>` | Set number of questions |
| `/quiz config window_minutes <n>` | Set answer window duration |
| `/quiz status` | Show current configuration |

See [docs/admin-guide.md](docs/admin-guide.md) for full details.

## Documentation

- [Architecture](docs/architecture.md) — Detailed system design and data flow
- [Deployment Guide](docs/deployment.md) — Step-by-step setup instructions
- [Admin Guide](docs/admin-guide.md) — Configuration and management
- [API Reference](docs/api-reference.md) — Endpoint specifications
- [Contributing](CONTRIBUTING.md) — Development setup and conventions
- [ADRs](docs/adr/) — Architecture Decision Records

## License

Internal use — Entain India.
