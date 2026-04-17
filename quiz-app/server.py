import os, json, random, re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

PORT = int(os.getenv("PORT", 3000))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QUIZ_TOPIC = os.getenv("QUIZ_TOPIC", "general knowledge and tech trivia")
QUESTIONS_PER_USER = 5
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_openai = None
def get_openai():
    global _openai
    if not _openai:
        _openai = OpenAI(api_key=OPENAI_API_KEY)
    return _openai

app = Flask(__name__, static_folder="public", static_url_path="")

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def read_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text())

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def quiz_path(date):     return DATA_DIR / f"quiz-{date}.json"
def sessions_path(date):  return DATA_DIR / f"sessions-{date}.json"
def results_path(date):   return DATA_DIR / f"results-{date}.json"
def leaderboard_path():   return DATA_DIR / "leaderboard.json"

def get_leaderboard():    return read_json(leaderboard_path(), [])
def save_leaderboard(lb): write_json(leaderboard_path(), lb)

def generate_quiz():
    date = today_str()
    qp = quiz_path(date)
    if qp.exists():
        print(f"Quiz for {date} already exists, skipping.")
        return
    print(f"Generating quiz for {date}...")
    resp = get_openai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": (
            f"Generate exactly 50 multiple-choice questions about: {QUIZ_TOPIC}.\n"
            "Return ONLY a JSON array of objects with keys: \"text\", \"options\" "
            "(object with keys A,B,C,D), \"correct\" (one of A,B,C,D).\n"
            "No markdown, no explanation, just the JSON array."
        )}],
        temperature=0.8,
        max_tokens=16000,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```json?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    questions = json.loads(raw)
    write_json(qp, {"date": date, "topic": QUIZ_TOPIC, "questions": questions})
    print(f"Quiz for {date} saved ({len(questions)} questions).")

# --- Routes ---

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.post("/api/start")
def start_quiz():
    body = request.json or {}
    name, email = body.get("name"), body.get("email")
    if not name or not email:
        return jsonify(error="Name and email are required."), 400

    date = today_str()
    quiz = read_json(quiz_path(date), None)
    if not quiz:
        return jsonify(error="No quiz available today. Check back soon!"), 404

    results = read_json(results_path(date), [])
    if any(r["email"] == email for r in results):
        return jsonify(error="already_submitted", message="You've already taken today's quiz!"), 409

    sessions = read_json(sessions_path(date), {})
    if email in sessions:
        s = sessions[email]
        questions = [{"id": i, "text": quiz["questions"][i]["text"], "options": quiz["questions"][i]["options"]} for i in s["questionIds"]]
        return jsonify(date=date, topic=quiz["topic"], total=len(questions), questions=questions, startedAt=s["startedAt"], resumed=True)

    picked = random.sample(range(len(quiz["questions"])), QUESTIONS_PER_USER)
    started_at = datetime.now(timezone.utc).isoformat()
    sessions[email] = {"name": name, "questionIds": picked, "startedAt": started_at}
    write_json(sessions_path(date), sessions)

    questions = [{"id": i, "text": quiz["questions"][i]["text"], "options": quiz["questions"][i]["options"]} for i in picked]
    return jsonify(date=date, topic=quiz["topic"], total=len(questions), questions=questions, startedAt=started_at, resumed=False)

@app.post("/api/submit")
def submit_quiz():
    body = request.json or {}
    email, answers = body.get("email"), body.get("answers")
    if not email or not answers:
        return jsonify(error="Email and answers are required."), 400

    date = body.get("date") or today_str()
    quiz = read_json(quiz_path(date), None)
    if not quiz:
        return jsonify(error="No quiz for this date."), 404

    results = read_json(results_path(date), [])
    if any(r["email"] == email for r in results):
        return jsonify(error="already_submitted", message="You've already taken today's quiz!"), 409

    sessions = read_json(sessions_path(date), {})
    session = sessions.get(email)
    if not session:
        return jsonify(error="No active session. Please start the quiz first."), 400

    now = datetime.now(timezone.utc)
    started = datetime.fromisoformat(session["startedAt"])
    time_taken = int((now - started).total_seconds())

    correct = sum(1 for i in session["questionIds"] if answers.get(str(i)) == quiz["questions"][i]["correct"])
    total = len(session["questionIds"])
    score = round((correct / total) * 100)

    results.append({"name": session["name"], "email": email, "correct": correct, "total": total, "score": score, "timeTaken": time_taken, "submittedAt": now.isoformat()})
    write_json(results_path(date), results)

    del sessions[email]
    write_json(sessions_path(date), sessions)

    lb = get_leaderboard()
    existing = next((e for e in lb if e["email"] == email), None)
    if existing:
        existing["totalCorrect"] += correct
        existing["totalQuestions"] += total
        existing["quizzesTaken"] += 1
        existing["name"] = session["name"]
        existing["avgScore"] = round((existing["totalCorrect"] / existing["totalQuestions"]) * 100)
        existing["lastPlayed"] = date
    else:
        lb.append({"name": session["name"], "email": email, "totalCorrect": correct, "totalQuestions": total, "quizzesTaken": 1, "avgScore": score, "lastPlayed": date})
    lb.sort(key=lambda e: (-e["avgScore"], -e["totalCorrect"]))
    save_leaderboard(lb)

    return jsonify(correct=correct, total=total, score=score, timeTaken=time_taken)

@app.get("/api/leaderboard")
def leaderboard():
    return jsonify(get_leaderboard())

@app.get("/api/results/<date>")
def results(date):
    return jsonify(read_json(results_path(date), []))

# --- Scheduler: daily at 8 AM ---
scheduler = BackgroundScheduler()
scheduler.add_job(generate_quiz, "cron", hour=8)
scheduler.start()

if __name__ == "__main__":
    try:
        generate_quiz()
    except Exception as e:
        print(f"Startup quiz generation failed: {e}")
    app.run(host="0.0.0.0", port=PORT)
