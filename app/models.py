"""
Database models for the Task Manager application.

This module defines SQLAlchemy models representing the data structure
of the application. Each model maps to a database table.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app import db


class TaskStatus(str, Enum):
    """Enumeration of possible task statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    """Enumeration of possible task priorities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(db.Model):
    """
    Task model representing a to-do item.

    Attributes:
        id: Unique identifier for the task.
        title: Short title describing the task.
        description: Detailed description of the task.
        status: Current status (pending, in_progress, completed).
        priority: Task priority level (low, medium, high).
        due_date: Optional deadline for the task.
        created_at: Timestamp when the task was created.
        updated_at: Timestamp when the task was last modified.
    """

    __tablename__ = "tasks"

    id: int = db.Column(db.Integer, primary_key=True)
    title: str = db.Column(db.String(200), nullable=False)
    description: str = db.Column(db.Text, nullable=True)
    status: str = db.Column(
        db.String(20),
        nullable=False,
        default=TaskStatus.PENDING.value
    )
    priority: str = db.Column(
        db.String(20),
        nullable=False,
        default=TaskPriority.MEDIUM.value
    )
    due_date: datetime | None = db.Column(db.DateTime(timezone=True), nullable=True)
    estimated_minutes: int | None = db.Column(db.Integer, nullable=True)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    @staticmethod
    def _to_utc_iso(value: datetime | None) -> str | None:
        """
        Convert datetime to an ISO-8601 UTC string.

        SQLite commonly returns naive datetime values even when timezone-aware
        columns are declared. For API contracts, always normalize to UTC.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the task to a dictionary representation.

        Returns:
            Dictionary containing all task fields.
        """
        return {
            "id": self.id,
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
        """Return string representation of the task."""
        return f"<Task {self.id}: {self.title}>"
