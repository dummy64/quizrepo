# Deployment Guide

Step-by-step instructions to deploy the AI Quiz System.

## Prerequisites

- AWS account with permissions for Lambda, DynamoDB, API Gateway, EventBridge, Secrets Manager, Bedrock
- AWS CLI configured (`aws configure`)
- Python 3.9+
- Node.js 18+ (for CDK CLI)
- Slack workspace admin access
- Microsoft Teams channel with webhook permissions

## Step 1: Clone and Install

```bash
git clone <repo-url>
cd quizrepo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Step 2: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it `Quiz Bot`, select your workspace

### Bot Token Scopes

Under **OAuth & Permissions**, add these Bot Token Scopes:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Post quiz messages and results |
| `chat:write.public` | Post to channels the bot hasn't joined |
| `commands` | Handle `/quiz` slash command |

### Slash Command

Under **Slash Commands** → **Create New Command**:

| Field | Value |
|-------|-------|
| Command | `/quiz` |
| Request URL | `<AdminUrl>` (from CDK output, set after deploy) |
| Description | AI Quiz System admin commands |
| Usage Hint | `now \| config <key> [value] \| status` |

### Interactivity

Under **Interactivity & Shortcuts** → Enable → set Request URL to `<SlackInteractionsUrl>` (from CDK output, set after deploy).

### Install to Workspace

Under **Install App** → **Install to Workspace** → Authorize. Copy the **Bot User OAuth Token** (`xoxb-...`).

### Collect Values

You'll need:
- **Bot User OAuth Token** — from Install App page
- **Signing Secret** — from Basic Information → App Credentials
- **Channel ID** — right-click the target channel in Slack → Copy Link → extract the ID (e.g., `C0123456789`)

## Step 3: Create a Teams Incoming Webhook

1. In Microsoft Teams, go to the target channel
2. Click **⋯** → **Connectors** (or **Manage channel** → **Connectors**)
3. Find **Incoming Webhook** → **Configure**
4. Name it `Quiz Bot`, optionally upload an icon → **Create**
5. Copy the webhook URL

## Step 4: Configure AWS Secrets

Create the secret in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name quiz-system/secrets \
  --secret-string '{
    "SLACK_BOT_TOKEN": "xoxb-your-token-here",
    "SLACK_SIGNING_SECRET": "your-signing-secret",
    "SLACK_CHANNEL": "C0123456789",
    "TEAMS_WEBHOOK_URL": "https://your-org.webhook.office.com/webhookb2/..."
  }'
```

To update later:

```bash
aws secretsmanager update-secret \
  --secret-id quiz-system/secrets \
  --secret-string '{ ... }'
```

## Step 5: Enable Bedrock Model Access

1. Go to the [AWS Bedrock console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access** in the left sidebar
3. Request access to **Anthropic Claude 3 Sonnet** (or your preferred model)
4. Wait for access to be granted (usually instant)

If using a different model, update the `BEDROCK_MODEL_ID` environment variable in `infra/stack.py`.

## Step 6: Deploy with CDK

```bash
# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy
npx cdk deploy
```

CDK will output the following URLs:

```
Outputs:
QuizSystemStack.ApiUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/
QuizSystemStack.SlackEventsUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/slack/events
QuizSystemStack.SlackInteractionsUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/slack/interactions
QuizSystemStack.TeamsMessagesUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/teams/messages
QuizSystemStack.AdminUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/admin
```

## Step 7: Update Slack App URLs

Go back to your Slack app settings and update:

1. **Slash Commands** → Edit `/quiz` → set Request URL to the `AdminUrl` output
2. **Interactivity & Shortcuts** → set Request URL to the `SlackInteractionsUrl` output

## Step 8: Set Initial Configuration

Use the `/quiz` command in Slack or call the admin API directly:

```bash
# Set quiz topic
curl -X POST <AdminUrl> -d "text=config topic general knowledge and tech trivia"

# Set number of questions
curl -X POST <AdminUrl> -d "text=config num_questions 5"

# Set answer window (minutes)
curl -X POST <AdminUrl> -d "text=config window_minutes 120"
```

## Step 9: Test

Trigger a quiz manually:

```bash
# Via Slack
/quiz now

# Or via API
curl -X POST <AdminUrl> -d "text=now"
```

Verify:
1. Quiz appears in both Slack and Teams channels
2. You can select answers and submit
3. After the window closes (or wait for the 15-min scorer), results are published

## Updating

To update after code changes:

```bash
npx cdk deploy
```

## Teardown

```bash
npx cdk destroy
```

Note: DynamoDB tables have `RemovalPolicy.DESTROY` set, so they will be deleted. Remove this in production if you want to retain data.
