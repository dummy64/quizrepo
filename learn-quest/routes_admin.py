from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db import get_db
from quiz_gen import generate_questions, fetch_url_text

router = APIRouter()


class ContentReq(BaseModel):
    title: str
    topic: str
    url: Optional[str] = None
    body: Optional[str] = None

@router.post("/content")
def add_content(req: ContentReq):
    """Admin submits learning content (URL or text). AI generates quiz from it."""
    if not req.url and not req.body:
        raise HTTPException(400, "Provide either url or body text.")

    text = req.body
    if req.url:
        text = fetch_url_text(req.url)

    conn = get_db()
    try:
        from routes_quiz import today_str
        # Generate questions from content
        questions = generate_questions(req.topic, count=50, content_text=text)

        # Store quiz
        conn.execute("INSERT INTO quizzes (date, topic, source) VALUES (?, ?, 'content')", (today_str(), req.topic))
        quiz_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for q in questions:
            conn.execute(
                "INSERT INTO questions (quiz_id, text, option_a, option_b, option_c, option_d, correct, explanation) VALUES (?,?,?,?,?,?,?,?)",
                (quiz_id, q["text"], q["options"]["A"], q["options"]["B"], q["options"]["C"], q["options"]["D"], q["correct"], q.get("explanation", "")),
            )

        # Store content reference
        conn.execute("INSERT INTO content (title, body, url, topic, quiz_id) VALUES (?,?,?,?,?)",
                     (req.title, req.body, req.url, req.topic, quiz_id))
        conn.commit()
        return {"quiz_id": quiz_id, "questions_generated": len(questions)}
    finally:
        conn.close()


class TeamReq(BaseModel):
    name: str

@router.post("/teams")
def create_team(req: TeamReq):
    conn = get_db()
    try:
        conn.execute("INSERT INTO teams (name) VALUES (?)", (req.name,))
        conn.commit()
        return {"ok": True}
    except Exception:
        raise HTTPException(409, "Team already exists.")
    finally:
        conn.close()


@router.get("/users")
def list_users():
    conn = get_db()
    try:
        users = conn.execute("SELECT u.id, u.name, u.email, u.xp, u.level, u.streak, t.name as team_name FROM users u LEFT JOIN teams t ON u.team_id=t.id ORDER BY u.xp DESC").fetchall()
        return [dict(u) for u in users]
    finally:
        conn.close()


@router.get("/stats")
def stats():
    conn = get_db()
    try:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        total_quizzes = conn.execute("SELECT COUNT(*) as c FROM quizzes").fetchone()["c"]
        total_submissions = conn.execute("SELECT COUNT(DISTINCT user_id || quiz_id) as c FROM xp_log").fetchone()["c"]
        avg_score = conn.execute("""
            SELECT COALESCE(AVG(CAST(is_correct AS FLOAT)) * 100, 0) as avg FROM responses
        """).fetchone()["avg"]

        # Per-topic breakdown
        topics = conn.execute("""
            SELECT q.topic, COUNT(DISTINCT xl.user_id) as participants, AVG(xl.xp_earned) as avg_xp
            FROM xp_log xl JOIN quizzes q ON xl.quiz_id=q.id GROUP BY q.topic
        """).fetchall()

        # Team standings
        teams = conn.execute("""
            SELECT t.name, COUNT(u.id) as members, COALESCE(AVG(u.xp), 0) as avg_xp
            FROM teams t LEFT JOIN users u ON u.team_id=t.id GROUP BY t.id ORDER BY avg_xp DESC
        """).fetchall()

        return {
            "total_users": total_users, "total_quizzes": total_quizzes,
            "total_submissions": total_submissions, "avg_score": round(avg_score, 1),
            "topics": [dict(t) for t in topics], "teams": [dict(t) for t in teams],
        }
    finally:
        conn.close()
