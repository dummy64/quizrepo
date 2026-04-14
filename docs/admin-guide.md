# Admin Guide

## Overview

The AI Quiz System is managed through the `/quiz` slash command in Slack. All configuration is stored in DynamoDB and takes effect immediately.

## Commands

### Trigger a Quiz

```
/quiz now
```

Immediately triggers quiz generation and posting to all configured channels. Useful for testing or running ad-hoc quizzes outside the regular schedule.

### View Current Configuration

```
/quiz status
```

Shows all configuration values currently set. Any key not shown uses its default value.

### Set Configuration

```
/quiz config <key> <value>
```

## Configuration Options

| Key | Default | Description |
|-----|---------|-------------|
| `topic` | `mix of general knowledge and tech trivia` | Theme for AI-generated questions. Can be anything: "cricket", "Python programming", "Entain products", "90s Bollywood" |
| `num_questions` | `5` | Number of questions per quiz (1–25) |
| `window_minutes` | `120` | How long the quiz stays open for answers, in minutes |
| `frequency` | Weekdays 10:00 AM UTC | Quiz schedule (configured via CDK, not slash command) |

### Examples

```
/quiz config topic Indian history and culture
/quiz config num_questions 10
/quiz config window_minutes 60
/quiz config topic mix of tech trivia and cricket
```

## Scheduling

The default schedule is **weekdays at 10:00 AM UTC** (3:30 PM IST). This is configured as an EventBridge cron rule in `infra/stack.py`:

```python
events.Rule(
    self, "QuizSchedule",
    schedule=events.Schedule.cron(minute="0", hour="10", week_day="MON-FRI"),
    targets=[targets.LambdaFunction(quiz_generator)],
)
```

To change the schedule, modify this cron expression and redeploy:

```bash
npx cdk deploy
```

Common cron patterns:
- `cron(0 10 ? * MON-FRI *)` — Weekdays at 10 AM UTC
- `cron(0 4 ? * MON *)` — Mondays at 4 AM UTC (weekly)
- `cron(0 10 ? * * *)` — Every day at 10 AM UTC

## Scoring

- **10 points** per correct answer
- **Speed bonus** for perfect scores: 1st place gets +5, 2nd +4, 3rd +3, 4th +2, 5th +1
- Late submissions (after the answer window) are rejected
- Duplicate submissions are rejected — only the first submission counts

## Leaderboard

Two leaderboards are maintained:

1. **Daily** (`daily:YYYY-MM-DD`) — Scores for a single day's quiz
2. **All-time** (`alltime`) — Cumulative scores across all quizzes

Results are published automatically after the answer window closes and scoring completes. The scorer runs every 15 minutes, so results appear within 15 minutes of the window closing.

## Troubleshooting

### Quiz not posting

1. Check that the Slack bot token and channel ID are correct in Secrets Manager
2. Verify the bot has been invited to the target channel
3. Check Lambda logs in CloudWatch: look for the `QuizGenerator` and `SlackBot` function logs

### Answers not being recorded

1. Verify the Interactivity URL in Slack app settings matches the `SlackInteractionsUrl` CDK output
2. Check the `AnswerCollector` Lambda logs
3. Ensure the quiz hasn't expired (check `closes_at` in the Quizzes table)

### Results not appearing

1. The scorer runs every 15 minutes — wait for the next cycle
2. Check the `Scorer` and `ResultsPublisher` Lambda logs
3. Verify the quiz status changed from `active` to `scored` in the Quizzes table
