from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_db

router = APIRouter()


class RegisterReq(BaseModel):
    name: str
    email: str
    team_id: int


@router.post("/register")
def register(req: RegisterReq):
    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (req.email,)).fetchone()
        if existing:
            raise HTTPException(409, "Email already registered.")
        conn.execute("INSERT INTO users (name, email, team_id) VALUES (?,?,?)", (req.name, req.email, req.team_id))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
        return dict(user)
    finally:
        conn.close()


@router.get("/profile/{email}")
def profile(email: str):
    conn = get_db()
    try:
        user = conn.execute("SELECT u.*, t.name as team_name FROM users u LEFT JOIN teams t ON u.team_id=t.id WHERE u.email=?", (email,)).fetchone()
        if not user:
            raise HTTPException(404, "User not found.")
        u = dict(user)
        badges = conn.execute(
            "SELECT b.key, b.name, b.icon, b.description, ub.earned_at FROM user_badges ub JOIN badges b ON ub.badge_id=b.id WHERE ub.user_id=?",
            (u["id"],)
        ).fetchall()
        u["badges"] = [dict(b) for b in badges]
        return u
    finally:
        conn.close()


@router.get("/teams")
def list_teams():
    conn = get_db()
    try:
        teams = conn.execute("SELECT t.*, COUNT(u.id) as member_count FROM teams t LEFT JOIN users u ON u.team_id=t.id GROUP BY t.id").fetchall()
        return [dict(t) for t in teams]
    finally:
        conn.close()


@router.post("/admin/assign-team")
def assign_team(email: str, team_id: int):
    conn = get_db()
    try:
        r = conn.execute("UPDATE users SET team_id=? WHERE email=?", (team_id, email))
        conn.commit()
        if r.rowcount == 0:
            raise HTTPException(404, "User not found.")
        return {"ok": True}
    finally:
        conn.close()
