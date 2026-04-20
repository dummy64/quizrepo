from db import get_db
from quiz_gen import generate_questions
from datetime import date


def pick_weak_topic() -> str:
    """Analyze past scores per topic, return the weakest one."""
    conn = get_db()
    try:
        topics_str = conn.execute("SELECT value FROM config WHERE key='default_topics'").fetchone()
        if not topics_str:
            return "general knowledge"
        all_topics = [t.strip() for t in topics_str["value"].split(",")]

        # Get avg correctness per topic
        rows = conn.execute("""
            SELECT q.topic, AVG(CAST(r.is_correct AS FLOAT)) as avg_correct
            FROM responses r
            JOIN questions qu ON r.question_id=qu.id
            JOIN quizzes q ON qu.quiz_id=q.id
            GROUP BY q.topic
        """).fetchall()

        scored = {r["topic"]: r["avg_correct"] for r in rows}

        # Topics never quizzed get priority, then lowest scoring
        unquizzed = [t for t in all_topics if t not in scored]
        if unquizzed:
            import random
            return random.choice(unquizzed)

        return min(scored, key=scored.get)
    finally:
        conn.close()


def generate_daily_quiz():
    """Generate today's quiz with weak-topic selection."""
    conn = get_db()
    try:
        today = date.today().isoformat()
        existing = conn.execute("SELECT id FROM quizzes WHERE date=?", (today,)).fetchone()
        if existing:
            print(f"Quiz for {today} already exists, skipping.")
            return

        topic = pick_weak_topic()
        count = int(conn.execute("SELECT value FROM config WHERE key='questions_per_quiz'").fetchone()["value"])

        print(f"Generating quiz for {today} on topic: {topic} ({count} questions)...")
        questions = generate_questions(topic, count)

        conn.execute("INSERT INTO quizzes (date, topic, source) VALUES (?, ?, 'ai')", (today, topic))
        quiz_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for q in questions:
            conn.execute(
                "INSERT INTO questions (quiz_id, text, option_a, option_b, option_c, option_d, correct, explanation) VALUES (?,?,?,?,?,?,?,?)",
                (quiz_id, q["text"], q["options"]["A"], q["options"]["B"], q["options"]["C"], q["options"]["D"], q["correct"], q.get("explanation", "")),
            )
        conn.commit()
        print(f"Quiz {quiz_id} saved ({len(questions)} questions on '{topic}').")
    finally:
        conn.close()
