"""
Unit tests for task-service SQLAlchemy model logic.

Validates default column values, serialization via ``to_dict()``, and
optional field handling on the Task model without touching HTTP endpoints.

Key SDET Concepts Demonstrated:
- Model-level unit testing independent of HTTP layer
- Verifying ORM defaults (status, priority, timestamps)
- Serialization round-trip checks (due_date ISO format)
- Nullable / optional field coverage (estimated_minutes)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.tasks.task_app.models import Task, TaskPriority, TaskStatus

pytestmark = pytest.mark.unit


def test_task_defaults_and_to_dict(db_session):
    """Test that a Task created with only required fields gets correct defaults."""
    # Arrange
    task = Task(user_id=1, title="Test Task")

    # Act
    db_session.session.add(task)
    db_session.session.commit()
    data = task.to_dict()

    # Assert
    assert data["user_id"] == 1
    assert data["title"] == "Test Task"
    assert data["status"] == TaskStatus.PENDING.value
    assert data["priority"] == TaskPriority.MEDIUM.value
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_task_due_date_serialization(db_session):
    """Test that due_date is correctly round-tripped through to_dict() as ISO 8601."""
    # Arrange
    due_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    task = Task(user_id=1, title="Due Date Task", due_date=due_date)

    # Act
    db_session.session.add(task)
    db_session.session.commit()
    data = task.to_dict()

    # Assert
    parsed = datetime.fromisoformat(data["due_date"])
    if parsed.tzinfo is None:
        expected = due_date.replace(tzinfo=None)
    else:
        expected = due_date.astimezone(parsed.tzinfo)
    assert parsed == expected


def test_task_with_estimated_minutes(db_session):
    """Test that estimated_minutes is stored and serialized when provided."""
    # Arrange
    task = Task(user_id=1, title="Estimated Task", estimated_minutes=30)

    # Act
    db_session.session.add(task)
    db_session.session.commit()
    data = task.to_dict()

    # Assert
    assert data["estimated_minutes"] == 30


def test_task_estimated_minutes_defaults_to_none(db_session):
    """Test that estimated_minutes defaults to None when not provided."""
    # Arrange
    task = Task(user_id=1, title="No Estimate Task")

    # Act
    db_session.session.add(task)
    db_session.session.commit()
    data = task.to_dict()

    # Assert
    assert data["estimated_minutes"] is None
