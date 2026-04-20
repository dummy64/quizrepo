import os
from contextlib import contextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from db import init_db, get_db

app = FastAPI(title="LearnQuest")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


@contextmanager
def db():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    init_db()
    # Schedule daily quiz generation at 8 AM
    from apscheduler.schedulers.background import BackgroundScheduler
    from scheduler import generate_daily_quiz
    sched = BackgroundScheduler()
    sched.add_job(generate_daily_quiz, "cron", hour=8, minute=0)
    sched.start()
    # Generate today's quiz in background thread (non-blocking)
    import threading
    threading.Thread(target=_gen_quiz_safe, daemon=True).start()


def _gen_quiz_safe():
    from scheduler import generate_daily_quiz
    try:
        generate_daily_quiz()
    except Exception as e:
        print(f"Startup quiz generation failed: {e}")


@app.get("/health")
def health():
    with db() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    return {"status": "ok", "tables": tables}


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# --- Import route modules ---
from routes_auth import router as auth_router
from routes_quiz import router as quiz_router
from routes_admin import router as admin_router
from routes_leaderboard import router as lb_router

app.include_router(auth_router, prefix="/api")
app.include_router(quiz_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(lb_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
