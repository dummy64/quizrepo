# API Reference

Base URL: `<ApiUrl>` (from CDK output after deployment)

## Endpoints

### POST /admin

Handles `/quiz` slash commands from Slack.

**Request** (Slack slash command payload, `application/x-www-form-urlencoded`):

| Field | Description |
|-------|-------------|
| `text` | Command text (e.g., `now`, `config topic cricket`, `status`) |
| `user_id` | Slack user ID of the admin |
| `channel_id` | Channel where command was invoked |

**Response** (`application/json`):

```json
{
  "response_type": "ephemeral",
  "text": "🚀 Quiz generation triggered! It will be posted shortly."
}
```

---

### POST /slack/interactions

Handles Slack Block Kit interactive payloads (button clicks, quiz submissions).

**Request** (`application/x-www-form-urlencoded`):

| Field | Description |
|-------|-------------|
| `payload` | JSON-encoded Slack interaction payload |

The interaction payload contains:

```json
{
  "type": "block_actions",
  "user": { "id": "U123", "name": "jdoe" },
  "actions": [
    {
      "action_id": "submit_quiz",
      "value": "quiz-20260412-abc123"
    }
  ],
  "channel": { "id": "C123" }
}
```

**Response**: `200 OK` (empty body). Confirmation sent as ephemeral message via Slack API.

---

### POST /slack/events

Reserved for Slack Events API (URL verification and event subscriptions).

**Request** (URL verification):

```json
{
  "type": "url_verification",
  "challenge": "abc123"
}
```

**Response**: Returns the challenge string.

---

### POST /teams/messages

Handles Teams Adaptive Card submissions.

**Request** (`application/json`):

```json
{
  "value": {
    "action": "submit_quiz",
    "quiz_id": "quiz-20260412-abc123",
    "quiz-20260412-abc123-q0": "B",
    "quiz-20260412-abc123-q1": "A",
    "quiz-20260412-abc123-q2": "C"
  },
  "from": {
    "aadObjectId": "user-aad-id",
    "name": "Jane Doe"
  }
}
```

**Response** (`application/json`):

```json
{
  "statusCode": 200,
  "type": "message",
  "text": "Answers submitted!"
}
```

---

### POST /answers

Direct answer submission endpoint (used internally by bot Lambdas).

**Request** (`application/json`):

```json
{
  "quiz_id": "quiz-20260412-abc123",
  "user_id": "U123",
  "platform": "slack",
  "display_name": "Jane Doe",
  "answers": {
    "quiz-20260412-abc123-q0": "B",
    "quiz-20260412-abc123-q1": "A",
    "quiz-20260412-abc123-q2": "C",
    "quiz-20260412-abc123-q3": "D",
    "quiz-20260412-abc123-q4": "A"
  }
}
```

**Response** (`application/json`):

Success:
```json
{ "status": "ok", "message": "Answers submitted!" }
```

Duplicate:
```json
{ "status": "duplicate", "message": "You already submitted answers for this quiz." }
```

Expired:
```json
{ "status": "closed", "message": "This quiz is no longer accepting answers." }
```

## Internal Lambda Invocations

These are not HTTP endpoints — they are Lambda-to-Lambda invocations.

### Quiz Generator → Slack Bot / Teams Bot

Payload passed when posting a quiz to channels:

```json
{
  "quiz_id": "quiz-20260412-abc123",
  "channel": "C0123456789"
}
```

### Scorer → Results Publisher

Payload passed after scoring completes:

```json
{
  "quiz_date": "2026-04-12"
}
```

## Authentication

- **Slack endpoints**: Verified using Slack request signing (HMAC-SHA256 with signing secret)
- **Teams endpoints**: Validated via Adaptive Card submission structure
- **Admin endpoint**: Slack slash command verification (same signing mechanism)
- **Answers endpoint**: No external auth (intended for internal Lambda-to-Lambda use via API Gateway)

## Rate Limits

- API Gateway default throttle: 10,000 requests/second
- Lambda concurrency: AWS account default (1,000 concurrent)
- DynamoDB: PAY_PER_REQUEST (auto-scales)
