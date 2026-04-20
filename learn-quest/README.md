# LearnQuest

A gamified learning platform for teams. Daily quizzes with rotating topics, XP/levels/streaks/badges, team competitions, and AI-generated content.

## Features

- **Daily quizzes** — 5 random questions from a pool of 50+ AI-generated questions
- **Smart topic rotation** — AI analyzes past scores and picks the weakest topic for the next quiz
- **Gamification** — XP, levels (12 levels), streaks (3/7/30-day multipliers), 8 badges
- **Team competitions** — Weekly/monthly team leaderboards by average XP
- **Learn-then-quiz** — Admins submit articles/URLs, AI generates quizzes from them
- **Session resume** — Refresh mid-quiz? Your progress and timer continue
- **Dark gaming UI** — Flashy animations, confetti, smooth transitions

## Tech Stack

- **Backend**: FastAPI + SQLite + APScheduler
- **Frontend**: Single HTML/JS page (no framework)
- **AI**: OpenAI ChatGPT (gpt-4o-mini) for quiz generation

## Setup

```bash
cd learn-quest
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=sk-...

# Start the server
python3 app.py
```

Open **http://localhost:8000**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/register` | Register user (name, email, team_id) |
| GET | `/api/profile/{email}` | Get user profile with badges |
| GET | `/api/teams` | List all teams |
| POST | `/api/admin/assign-team` | Admin: reassign user to team |
| GET | `/api/quiz/today` | Get today's quiz info |
| POST | `/api/quiz/start` | Start quiz session (returns 5 random questions) |
| POST | `/api/quiz/submit` | Submit answers (scores, awards XP/badges) |
| GET | `/api/leaderboard` | Get leaderboard (type=individual|team, period=daily|weekly|monthly|alltime) |
| POST | `/api/admin/content` | Admin: submit content for quiz generation |
| POST | `/api/admin/teams` | Admin: create new team |
| GET | `/api/admin/stats` | Admin: participation stats, team standings |

## Deployment (EC2 t3.micro)

See `DEPLOY.md` for full instructions.

```bash
# On server
git clone your-repo
cd learn-quest
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
nohup python3 app.py > server.log 2>&1 &

# Setup systemd service for auto-restart
sudo tee /etc/systemd/system/learn-quest.service <<EOF
[Unit]
Description=LearnQuest
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/learn-quest
EnvironmentFile=/home/ec2-user/learn-quest/.env
ExecStart=/usr/bin/python3 app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable learn-quest
sudo systemctl start learn-quest
```

## Project Structure

```
learn-quest/
├── app.py              # FastAPI app + scheduler
├── db.py               # SQLite schema + seeds
├── quiz_gen.py         # OpenAI quiz generation
├── scheduler.py        # Daily quiz generation with weak-topic analysis
├── routes_auth.py      # Auth + team endpoints
├── routes_quiz.py      # Quiz start/submit + XP engine + badges
├── routes_admin.py     # Admin endpoints
├── routes_leaderboard.py
├── requirements.txt
├── static/
│   └── index.html      # Full SPA frontend
├── data/
│   └── learn_quest.db  # SQLite database
└── DEPLOY.md           # Deployment guide
```

## License

Internal use — Entain India.
