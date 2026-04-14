from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class QuizStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    SCORED = "scored"


class Question(BaseModel):
    question_id: str
    text: str
    options: Dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_option: str
    explanation: str


class Quiz(BaseModel):
    quiz_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    topic: str
    questions: List[Question]
    status: QuizStatus = QuizStatus.PENDING
    window_minutes: int = 120
    closes_at: Optional[str] = None


class UserResponse(BaseModel):
    quiz_id: str
    user_id: str
    platform: str  # "slack" or "teams"
    display_name: str
    answers: Dict[str, str]  # {question_id: selected_option}
    submitted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class LeaderboardEntry(BaseModel):
    period: str  # "daily:2026-04-12" or "weekly:2026-W15" or "alltime"
    user_id: str
    display_name: str
    score: int = 0
    correct: int = 0
    total: int = 0
    quizzes_taken: int = 0


class QuizConfig(BaseModel):
    config_key: str
    value: str
