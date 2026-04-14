# Architecture

## Overview

The AI Quiz System is a fully serverless application running on AWS. It uses an event-driven architecture where EventBridge schedules trigger Lambda functions that coordinate quiz generation, distribution, scoring, and results publishing.

## System Components

### 1. Quiz Generator Lambda

- **Trigger:** EventBridge cron rule (weekdays 10:00 AM UTC) or on-demand via admin command
- **Process:**
  1. Reads configuration (topic, num_questions, window_minutes) from the Config DynamoDB table
  2. Calls AWS Bedrock Converse API with Claude to generate quiz questions as structured JSON
  3. Stores the quiz in the Quizzes table with status `active` and a `closes_at` timestamp
  4. Returns the quiz_id for downstream Lambdas to post to channels

### 2. Slack Bot Lambda

- **Trigger:** Invoked by quiz generator (to post quiz) or API Gateway (to handle interactions)
- **Quiz posting:** Builds a Slack Block Kit message with a header, questions with option buttons (A/B/C/D), and a Submit button
- **Answer handling:** Verifies the Slack request signature, parses the interaction payload, extracts selected answers, and calls the shared `save_response` function
- **Responds** with an ephemeral message confirming submission

### 3. Teams Bot Lambda

- **Trigger:** Invoked by quiz generator (to post quiz) or API Gateway (to handle card submissions)
- **Quiz posting:** Builds an Adaptive Card with `Input.ChoiceSet` per question and an `Action.Submit` button, posts via incoming webhook
- **Answer handling:** Parses the card submission payload, extracts answers, and calls the shared `save_response` function

### 4. Answer Collector Lambda

- **Trigger:** API Gateway POST `/answers`
- **Shared logic** used by both Slack and Teams bots
- **Checks:**
  - Quiz is still `active` and current time is before `closes_at` → rejects late submissions
  - User hasn't already submitted → rejects duplicates
- **Stores** the response in the Responses table

### 5. Scorer Lambda

- **Trigger:** EventBridge rate rule (every 15 minutes)
- **Process:**
  1. Scans the Quizzes table for quizzes with status `active` and `closes_at` in the past
  2. For each quiz, queries all responses from the Responses table
  3. Compares answers against correct options: 10 points per correct answer + speed bonus (up to 5 points for perfect scores, ranked by submission time)
  4. Updates the Leaderboard table for both `daily:<date>` and `alltime` periods using atomic DynamoDB updates
  5. Marks the quiz as `scored`
  6. Async-invokes the Results Publisher Lambda

### 6. Results Publisher Lambda

- **Trigger:** Invoked by Scorer Lambda after scoring completes
- **Process:**
  1. Queries the Leaderboard table's `by_score` LSI for top 10 daily and top 10 all-time entries
  2. Formats results with medal emojis (🥇🥈🥉) and score details
  3. Posts to Slack channel via Block Kit message
  4. Posts to Teams channel via Adaptive Card webhook

### 7. Admin Lambda

- **Trigger:** API Gateway POST `/admin` (Slack slash command)
- **Commands:** `/quiz now`, `/quiz config <key> [value]`, `/quiz status`
- **Reads/writes** the Config DynamoDB table
- **Can invoke** the Quiz Generator Lambda on-demand

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUIZ LIFECYCLE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. GENERATE                                                    │
│     EventBridge (cron) ──► Quiz Generator ──► Bedrock Claude    │
│                                    │                            │
│                                    ▼                            │
│                            DynamoDB: Quizzes                    │
│                            status: "active"                     │
│                            closes_at: now + window_minutes      │
│                                                                 │
│  2. DISTRIBUTE                                                  │
│     Quiz Generator ──► Slack Bot ──► Slack Channel              │
│                    └──► Teams Bot ──► Teams Channel              │
│                                                                 │
│  3. COLLECT (during answer window)                              │
│     User clicks answer ──► API Gateway ──► Answer Collector     │
│                                                  │              │
│                                                  ▼              │
│                                          DynamoDB: Responses    │
│                                          (dedup + expiry check) │
│                                                                 │
│  4. SCORE (after window closes)                                 │
│     EventBridge (15 min) ──► Scorer                             │
│                                │                                │
│                                ├──► Read Responses              │
│                                ├──► Calculate scores            │
│                                ├──► Update DynamoDB: Leaderboard│
│                                └──► Mark quiz "scored"          │
│                                                                 │
│  5. PUBLISH                                                     │
│     Scorer ──► Results Publisher ──► Slack Channel               │
│                                 └──► Teams Channel              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## DynamoDB Tables

### Quizzes

| Attribute | Type | Description |
|-----------|------|-------------|
| `quiz_id` (PK) | String | `quiz-YYYYMMDD-<6hex>` |
| `created_at` | String | ISO 8601 timestamp |
| `topic` | String | Quiz topic/theme |
| `questions` | List | Array of question objects |
| `status` | String | `pending` → `active` → `closed` → `scored` |
| `window_minutes` | Number | Answer window duration |
| `closes_at` | String | ISO 8601 timestamp when quiz stops accepting answers |

### Responses

| Attribute | Type | Description |
|-----------|------|-------------|
| `quiz_id` (PK) | String | References Quizzes table |
| `user_id` (SK) | String | Slack user ID or Teams AAD object ID |
| `platform` | String | `slack` or `teams` |
| `display_name` | String | User's display name |
| `answers` | Map | `{question_id: selected_option}` |
| `submitted_at` | String | ISO 8601 timestamp |

### Leaderboard

| Attribute | Type | Description |
|-----------|------|-------------|
| `period` (PK) | String | `daily:YYYY-MM-DD` or `alltime` |
| `user_id` (SK) | String | User identifier |
| `display_name` | String | User's display name |
| `score` | Number | Cumulative score for the period |
| `correct` | Number | Total correct answers |
| `total` | Number | Total questions attempted |
| `quizzes_taken` | Number | Number of quizzes participated in |

LSI: `by_score` — sorts by `score` descending for leaderboard queries.

### Config

| Attribute | Type | Description |
|-----------|------|-------------|
| `config_key` (PK) | String | Configuration key name |
| `value` | String | Configuration value |

## Scoring Algorithm

1. Each correct answer = **10 points**
2. Speed bonus for perfect scores: the first person to submit a perfect score gets **+5 bonus points**, second gets +4, third +3, etc.
3. Late submissions (after `closes_at`) are rejected
4. Duplicate submissions are rejected (first submission counts)

## Infrastructure

All resources are defined in AWS CDK (Python) in `infra/stack.py`:

- **7 Lambda functions** with least-privilege IAM policies
- **4 DynamoDB tables** with PAY_PER_REQUEST billing
- **1 API Gateway** (REST) with 5 endpoints
- **2 EventBridge rules** (quiz schedule + scorer schedule)
- **1 Secrets Manager secret** for Slack/Teams credentials
