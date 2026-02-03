"""
Unit tests for Task model logic.
"""

from datetime import datetime, timezone
import pytest

from app.models import Task, TaskStatus, TaskPriority


pytestmark = pytest.mark.unit


def test_task_defaults_and_to_dict(db_session):
    task = Task(title="Test Task")
    db_session.session.add(task)
    db_session.session.commit()

    data = task.to_dict()

    assert data["title"] == "Test Task"
    assert data["status"] == TaskStatus.PENDING.value
    assert data["priority"] == TaskPriority.MEDIUM.value
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_task_due_date_serialization(db_session):
    due_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    task = Task(title="Due Date Task", due_date=due_date)
    db_session.session.add(task)
    db_session.session.commit()

    data = task.to_dict()

    parsed = datetime.fromisoformat(data["due_date"])
    if parsed.tzinfo is None:
        expected = due_date.replace(tzinfo=None)
    else:
        expected = due_date.astimezone(parsed.tzinfo)
    assert parsed == expected


def test_task_with_estimated_minutes(db_session):
    """Test that estimated_minutes is correctly stored and serialized."""
    # Arrange
    task = Task(title="Estimated Task", estimated_minutes=30)
    db_session.session.add(task)
    db_session.session.commit()

    # Act
    data = task.to_dict()

    # Assert
    assert data["estimated_minutes"] == 30


def test_task_estimated_minutes_defaults_to_none(db_session):
    """Test that estimated_minutes defaults to None when not provided."""
    # Arrange
    task = Task(title="No Estimate Task")
    db_session.session.add(task)
    db_session.session.commit()

    # Act
    data = task.to_dict()

    # Assert
    assert data["estimated_minutes"] is None
