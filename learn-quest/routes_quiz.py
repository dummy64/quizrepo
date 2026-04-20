import json, random
from datetime import datetime, date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_db

router = APIRouter()

LEVEL_THRESHOLDS = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5500, 7500, 10000]


def calc_level(xp: int) -> int:
    for i in range(len(LEVEL_THRESHOLDS) - 1, -1, -1):
        if xp >= LEVEL_THRESHOLDS[i]:
            return i + 1
    return 1


def today_str():
    return date.today().isoformat()


# --- GET today's quiz info ---
@router.get("/quiz/today")
def quiz_today():
    conn = get_db()
    try:
        quiz = conn.execute("SELECT * FROM quizzes WHERE date=?", (today_str(),)).fetchone()
        if not quiz:
            return {"available": False, "message": "No quiz available today. Check back soon!"}
        count = conn.execute("SELECT COUNT(*) as c FROM questions WHERE quiz_id=?", (quiz["id"],)).fetchone()["c"]
        return {"available": True, "quiz_id": quiz["id"], "topic": quiz["topic"], "date": quiz["date"], "total_questions": count}
    finally:
        conn.close()


# --- Start a quiz session ---
class StartReq(BaseModel):
    email: str

@router.post("/quiz/start")
def quiz_start(req: StartReq):
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
        if not user:
            raise HTTPException(404, "User not found. Please register first.")

        quiz = conn.execute("SELECT * FROM quizzes WHERE date=?", (today_str(),)).fetchone()
        if not quiz:
            raise HTTPException(404, "No quiz available today.")

        # Check existing session
        session = conn.execute("SELECT * FROM sessions WHERE user_id=? AND quiz_id=?", (user["id"], quiz["id"])).fetchone()

        if session and session["submitted"]:
            raise HTTPException(409, detail={"error": "already_submitted", "message": "You've already taken today's quiz!"})

        if session:
            # Resume — return same questions
            qids = json.loads(session["question_ids"])
            questions = []
            for qid in qids:
                q = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
                if q:
                    questions.append({"id": q["id"], "text": q["text"], "options": {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}})
            return {"quiz_id": quiz["id"], "topic": quiz["topic"], "questions": questions, "started_at": session["started_at"], "resumed": True}

        # New session — pick random questions
        per_user = int(conn.execute("SELECT value FROM config WHERE key='questions_per_user'").fetchone()["value"])
        all_q = conn.execute("SELECT id FROM questions WHERE quiz_id=?", (quiz["id"],)).fetchall()
        picked = random.sample([r["id"] for r in all_q], min(per_user, len(all_q)))

        conn.execute("INSERT INTO sessions (user_id, quiz_id, question_ids) VALUES (?,?,?)", (user["id"], quiz["id"], json.dumps(picked)))
        conn.commit()

        session = conn.execute("SELECT * FROM sessions WHERE user_id=? AND quiz_id=?", (user["id"], quiz["id"])).fetchone()
        questions = []
        for qid in picked:
            q = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
            questions.append({"id": q["id"], "text": q["text"], "options": {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}})

        return {"quiz_id": quiz["id"], "topic": quiz["topic"], "questions": questions, "started_at": session["started_at"], "resumed": False}
    finally:
        conn.close()


# --- Submit answers ---
class SubmitReq(BaseModel):
    email: str
    quiz_id: int
    answers: dict  # {question_id: "A"/"B"/"C"/"D"}

@router.post("/quiz/submit")
def quiz_submit(req: SubmitReq):
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
        if not user:
            raise HTTPException(404, "User not found.")

        session = conn.execute("SELECT * FROM sessions WHERE user_id=? AND quiz_id=?", (user["id"], req.quiz_id)).fetchone()
        if not session:
            raise HTTPException(400, "No active session.")
        if session["submitted"]:
            raise HTTPException(409, detail={"error": "already_submitted", "message": "Already submitted!"})

        # Calculate time server-side
        started = datetime.fromisoformat(session["started_at"])
        time_taken = int((datetime.utcnow() - started).total_seconds())

        # Score
        qids = json.loads(session["question_ids"])
        correct = 0
        total = len(qids)
        for qid in qids:
            q = conn.execute("SELECT correct FROM questions WHERE id=?", (qid,)).fetchone()
            user_ans = req.answers.get(str(qid), "")
            is_correct = 1 if user_ans == q["correct"] else 0
            if is_correct:
                correct += 1
            conn.execute("INSERT OR IGNORE INTO responses (user_id, quiz_id, question_id, answer, is_correct) VALUES (?,?,?,?,?)",
                         (user["id"], req.quiz_id, qid, user_ans, is_correct))

        # XP calculation
        base_xp = correct * 10
        speed_bonus = 5 if time_taken < 60 and correct > 0 else 0
        perfect_bonus = 20 if correct == total else 0

        # Streak
        yesterday = date.today().isoformat()  # simplified — check last_quiz_date
        last = user["last_quiz_date"]
        from datetime import timedelta
        is_consecutive = last == (date.today() - timedelta(days=1)).isoformat() if last else False
        new_streak = (user["streak"] + 1) if is_consecutive else 1

        streak_mult = 1.0
        if new_streak >= 7:
            streak_mult = 3.0
        elif new_streak >= 3:
            streak_mult = 2.0

        total_xp = int((base_xp + speed_bonus + perfect_bonus) * streak_mult)

        breakdown = json.dumps({"base": base_xp, "speed": speed_bonus, "perfect": perfect_bonus, "streak_mult": streak_mult})
        conn.execute("INSERT INTO xp_log (user_id, quiz_id, xp_earned, breakdown) VALUES (?,?,?,?)",
                     (user["id"], req.quiz_id, total_xp, breakdown))

        new_total_xp = user["xp"] + total_xp
        new_level = calc_level(new_total_xp)
        conn.execute("UPDATE users SET xp=?, level=?, streak=?, last_quiz_date=? WHERE id=?",
                     (new_total_xp, new_level, new_streak, today_str(), user["id"]))

        # Mark session submitted
        conn.execute("UPDATE sessions SET submitted=1 WHERE id=?", (session["id"],))
        conn.commit()

        # Award badges
        new_badges = check_and_award_badges(conn, user["id"], correct, total, time_taken, new_streak, new_total_xp, req.quiz_id)
        conn.commit()

        return {
            "correct": correct, "total": total, "score": round(correct / total * 100),
            "xp_earned": total_xp, "total_xp": new_total_xp, "level": new_level,
            "streak": new_streak, "time_taken": time_taken,
            "breakdown": json.loads(breakdown),
            "new_badges": new_badges,
            "level_up": new_level > user["level"],
        }
    finally:
        conn.close()


def check_and_award_badges(conn, user_id, correct, total, time_taken, streak, total_xp, quiz_id):
    """Check badge conditions and award new ones. Returns list of newly earned badges."""
    new_badges = []

    def award(badge_key):
        badge = conn.execute("SELECT * FROM badges WHERE key=?", (badge_key,)).fetchone()
        if not badge:
            return
        existing = conn.execute("SELECT id FROM user_badges WHERE user_id=? AND badge_id=?", (user_id, badge["id"])).fetchone()
        if not existing:
            conn.execute("INSERT INTO user_badges (user_id, badge_id) VALUES (?,?)", (user_id, badge["id"]))
            new_badges.append({"key": badge["key"], "name": badge["name"], "icon": badge["icon"]})

    # First quiz
    quiz_count = conn.execute("SELECT COUNT(*) as c FROM xp_log WHERE user_id=?", (user_id,)).fetchone()["c"]
    if quiz_count == 1:
        award("first_quiz")

    # Perfect score
    if correct == total:
        award("perfect_score")

    # Streaks
    if streak >= 3: award("streak_3")
    if streak >= 7: award("streak_7")
    if streak >= 30: award("streak_30")

    # Speed demon
    if time_taken < 30 and correct > 0:
        award("speed_demon")

    # Centurion
    if total_xp >= 1000:
        award("centurion")

    # Topic master — 5 perfect scores in one topic
    quiz = conn.execute("SELECT topic FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
    if quiz and correct == total:
        perfect_in_topic = conn.execute("""
            SELECT COUNT(*) as c FROM xp_log xl
            JOIN quizzes q ON xl.quiz_id=q.id
            WHERE xl.user_id=? AND q.topic=? AND json_extract(xl.breakdown, '$.perfect') = 20
        """, (user_id, quiz["topic"])).fetchone()["c"]
        if perfect_in_topic >= 5:
            award("topic_master")

    return new_badges
