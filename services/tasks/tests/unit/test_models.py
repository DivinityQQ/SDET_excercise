"""Unit tests for task service model logic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from task_app.models import Task, TaskPriority, TaskStatus

pytestmark = pytest.mark.unit


def test_task_defaults_and_to_dict(db_session):
    task = Task(user_id=1, title="Test Task")
    db_session.session.add(task)
    db_session.session.commit()

    data = task.to_dict()

    assert data["user_id"] == 1
    assert data["title"] == "Test Task"
    assert data["status"] == TaskStatus.PENDING.value
    assert data["priority"] == TaskPriority.MEDIUM.value
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_task_due_date_serialization(db_session):
    due_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    task = Task(user_id=1, title="Due Date Task", due_date=due_date)
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
    task = Task(user_id=1, title="Estimated Task", estimated_minutes=30)
    db_session.session.add(task)
    db_session.session.commit()

    data = task.to_dict()
    assert data["estimated_minutes"] == 30


def test_task_estimated_minutes_defaults_to_none(db_session):
    task = Task(user_id=1, title="No Estimate Task")
    db_session.session.add(task)
    db_session.session.commit()

    data = task.to_dict()
    assert data["estimated_minutes"] is None

