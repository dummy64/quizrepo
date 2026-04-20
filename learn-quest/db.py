import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "learn_quest.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    team_id INTEGER REFERENCES teams(id),
    is_admin INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    streak INTEGER DEFAULT 0,
    last_quiz_date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    topic TEXT NOT NULL,
    source TEXT DEFAULT 'ai',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct TEXT NOT NULL,
    explanation TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    question_ids TEXT NOT NULL,
    started_at TEXT DEFAULT (datetime('now')),
    submitted INTEGER DEFAULT 0,
    UNIQUE(user_id, quiz_id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    UNIQUE(user_id, question_id)
);

CREATE TABLE IF NOT EXISTS xp_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    xp_earned INTEGER NOT NULL,
    breakdown TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    badge_id INTEGER NOT NULL REFERENCES badges(id),
    earned_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT,
    url TEXT,
    topic TEXT NOT NULL,
    quiz_id INTEGER REFERENCES quizzes(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_TEAMS = ["Engineering", "Product", "Design", "Data Science", "QA", "DevOps", "Management"]

DEFAULT_BADGES = [
    ("first_quiz", "First Steps", "Completed your first quiz", "🎯"),
    ("streak_3", "On Fire", "3-day streak", "🔥"),
    ("streak_7", "Unstoppable", "7-day streak", "⚡"),
    ("streak_30", "Legend", "30-day streak", "👑"),
    ("perfect_score", "Perfectionist", "Got 100% on a quiz", "💯"),
    ("topic_master", "Topic Master", "5 perfect scores in one topic", "🧠"),
    ("speed_demon", "Speed Demon", "Finished a quiz under 30 seconds", "⚡"),
    ("centurion", "Centurion", "Earned 1000 XP total", "🏛️"),
]

DEFAULT_CONFIG = {
    "questions_per_quiz": "50",
    "questions_per_user": "5",
    "default_topics": "cloud computing,cybersecurity,python programming,data structures,system design,devops,general tech trivia",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)

    # Seed teams
    for team in DEFAULT_TEAMS:
        conn.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (team,))

    # Seed badges
    for key, name, desc, icon in DEFAULT_BADGES:
        conn.execute("INSERT OR IGNORE INTO badges (key, name, description, icon) VALUES (?,?,?,?)", (key, name, desc, icon))

    # Seed config
    for k, v in DEFAULT_CONFIG.items():
        conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()
