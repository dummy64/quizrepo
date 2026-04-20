from datetime import date, timedelta
from fastapi import APIRouter
from db import get_db

router = APIRouter()


@router.get("/leaderboard")
def leaderboard(type: str = "individual", period: str = "weekly"):
    conn = get_db()
    try:
        today = date.today()
        if period == "daily":
            start = today.isoformat()
        elif period == "weekly":
            start = (today - timedelta(days=today.weekday())).isoformat()
        elif period == "monthly":
            start = today.replace(day=1).isoformat()
        else:
            start = "2000-01-01"

        if type == "team":
            rows = conn.execute("""
                SELECT t.name as team_name, COUNT(DISTINCT u.id) as members,
                       COALESCE(SUM(xl.xp_earned), 0) as total_xp,
                       COALESCE(AVG(xl.xp_earned), 0) as avg_xp
                FROM teams t
                LEFT JOIN users u ON u.team_id=t.id
                LEFT JOIN xp_log xl ON xl.user_id=u.id AND xl.created_at >= ?
                GROUP BY t.id
                HAVING members > 0
                ORDER BY avg_xp DESC
            """, (start,)).fetchall()
            return [dict(r) for r in rows]
        else:
            rows = conn.execute("""
                SELECT u.name, u.email, u.level, u.streak, t.name as team_name,
                       COALESCE(SUM(xl.xp_earned), 0) as period_xp
                FROM users u
                LEFT JOIN teams t ON u.team_id=t.id
                LEFT JOIN xp_log xl ON xl.user_id=u.id AND xl.created_at >= ?
                GROUP BY u.id
                HAVING period_xp > 0
                ORDER BY period_xp DESC
                LIMIT 50
            """, (start,)).fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()
