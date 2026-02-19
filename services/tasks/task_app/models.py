"""
Database Models for the Task Service.

Defines the SQLAlchemy ORM model that represents a user-owned task, along
with the enumerations used for task status and priority.  Each task is
scoped to exactly one user via ``user_id``, which enables strict tenant
isolation -- users can only see and modify their own tasks.

Key Concepts Demonstrated:
- SQLAlchemy declarative ORM model with typed columns
- ``str, Enum`` inheritance for JSON-friendly enumeration values
- Timezone-aware datetime handling (UTC normalisation)
- Serialisation helper (``to_dict``) for JSON API responses
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from . import db


class TaskStatus(str, Enum):
    """
    Enumeration of possible task lifecycle statuses.

    Inherits from ``str`` so that each member's value is a plain string.
    This allows direct JSON serialisation (``json.dumps``) and seamless
    comparison with raw strings stored in the database column, without
    needing an explicit ``.value`` accessor in most contexts.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    """
    Enumeration of task priority levels.

    Inherits from ``str`` (like ``TaskStatus``) so enum members serialise
    directly to their string values, simplifying JSON responses and
    database storage.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(db.Model):
    """
    Task model owned by a single user.

    Represents an actionable item with a title, optional description,
    status, priority, optional due date and time estimate.

    Attributes:
        id: Auto-incrementing primary key.
        user_id: Foreign reference to the owning user (from the auth
            service).  Indexed for fast per-user queries.
        title: Short summary of the task (max 200 characters).
        description: Optional longer text with details about the task.
        status: Current lifecycle status (see ``TaskStatus``).
        priority: Importance level (see ``TaskPriority``).
        due_date: Optional timezone-aware deadline.
        estimated_minutes: Optional time estimate in minutes.
        created_at: Timestamp of task creation (UTC).
        updated_at: Timestamp of last modification (UTC, auto-updated).
    """

    __tablename__ = "tasks"

    id: int = db.Column(db.Integer, primary_key=True)
    # user_id enforces tenant isolation: every query in the API layer
    # filters by this value (sourced from the JWT) so that users can
    # never access tasks belonging to another user.
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
        """
        Convert a datetime to a UTC ISO-8601 string.

        SQLite does not store timezone information, so datetime values
        read back from the database may be *naive* (``tzinfo is None``)
        even though they were originally created in UTC.  This helper
        normalises that edge-case: naive datetimes are assumed UTC and
        get their ``tzinfo`` attached; aware datetimes are converted to
        UTC before formatting.

        Args:
            value: A datetime instance, or ``None``.

        Returns:
            An ISO-8601 formatted string in UTC, or ``None`` if the
            input was ``None``.
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
        Serialise the task to a JSON-safe dictionary.

        Returns:
            A dictionary containing all task fields with datetime values
            converted to UTC ISO-8601 strings.
        """
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
