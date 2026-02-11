"""Database models for task service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from task_app import db


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(db.Model):
    """Task model owned by a single user."""

    __tablename__ = "tasks"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, nullable=False, index=True)
    title: str = db.Column(db.String(200), nullable=False)
    description: str = db.Column(db.Text, nullable=True)
    status: str = db.Column(
        db.String(20),
        nullable=False,
        default=TaskStatus.PENDING.value,
    )
    priority: str = db.Column(
        db.String(20),
        nullable=False,
        default=TaskPriority.MEDIUM.value,
    )
    due_date: datetime | None = db.Column(db.DateTime(timezone=True), nullable=True)
    estimated_minutes: int | None = db.Column(db.Integer, nullable=True)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def _to_utc_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self._to_utc_iso(self.due_date),
            "estimated_minutes": self.estimated_minutes,
            "created_at": self._to_utc_iso(self.created_at),
            "updated_at": self._to_utc_iso(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Task {self.id}: {self.title}>"

