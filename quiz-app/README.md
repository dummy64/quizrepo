# Daily Quiz App

AI-powered daily quiz app with leaderboard tracking. Generates 50 multiple-choice questions daily using OpenAI, serves 5 random questions per user, and tracks scores over time.

## Features

- Daily quiz generation via OpenAI (gpt-4o-mini)
- 5 random questions per user per day
- Server-side timing (can't be cheated)
- Session resume if you leave mid-quiz
- One attempt per day per email
- Persistent leaderboard with average scores
- Auto-generates new quiz daily at 8 AM

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set your values:

```
OPENAI_API_KEY=your-key-here
PORT=3000
QUIZ_TOPIC=general knowledge and tech trivia
```

## Run

```bash
source venv/bin/activate
python server.py
```

Open http://localhost:3000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/start` | Start a quiz session (body: `{name, email}`) |
| POST | `/api/submit` | Submit answers (body: `{email, answers, date}`) |
| GET | `/api/leaderboard` | Get leaderboard |
| GET | `/api/results/<date>` | Get results for a specific date |

## Data Storage

JSON files in `data/`:
- `quiz-YYYY-MM-DD.json` — daily questions
- `sessions-YYYY-MM-DD.json` — active sessions
- `results-YYYY-MM-DD.json` — submitted results
- `leaderboard.json` — all-time leaderboard

## Production

Use gunicorn instead of the Flask dev server:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:3000 server:app
```
