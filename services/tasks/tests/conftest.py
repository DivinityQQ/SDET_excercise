"""Shared pytest fixtures for task service tests."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from faker import Faker

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_JWT_SECRET_KEY"] = "test-jwt-secret-key-for-local-tests-123456"

from shared.test_helpers import auth_headers, create_test_token
from task_app import create_app, db
from task_app.models import Task, TaskPriority, TaskStatus

fake = Faker()


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def test_token(app) -> str:
    return create_test_token(
        user_id=1,
        username="user_one",
        secret=app.config["JWT_SECRET_KEY"],
    )


@pytest.fixture
def second_user_token(app) -> str:
    return create_test_token(
        user_id=2,
        username="user_two",
        secret=app.config["JWT_SECRET_KEY"],
    )


@pytest.fixture
def api_headers(test_token) -> dict[str, str]:
    return auth_headers(test_token)


@pytest.fixture
def second_user_headers(second_user_token) -> dict[str, str]:
    return auth_headers(second_user_token)


@pytest.fixture
def task_factory(db_session):
    created_tasks = []

    def _create_task(
        *,
        user_id: int = 1,
        title: str | None = None,
        description: str | None = None,
        status: str = TaskStatus.PENDING.value,
        priority: str = TaskPriority.MEDIUM.value,
        due_date: datetime | None = None,
    ) -> Task:
        task = Task(
            user_id=user_id,
            title=title or fake.sentence(nb_words=4),
            description=description or fake.paragraph(),
            status=status,
            priority=priority,
            due_date=due_date,
        )
        db_session.session.add(task)
        db_session.session.commit()
        created_tasks.append(task)
        return task

    yield _create_task

    for task in created_tasks:
        task_id = getattr(task, "id", None)
        if not task_id:
            continue
        existing = db_session.session.get(Task, task_id)
        if existing:
            db_session.session.delete(existing)
    db_session.session.commit()


@pytest.fixture
def sample_task(task_factory) -> Task:
    return task_factory(
        user_id=1,
        title="Sample Task",
        description="This is a sample task for testing",
        status=TaskStatus.PENDING.value,
        priority=TaskPriority.MEDIUM.value,
    )


@pytest.fixture
def multiple_tasks(task_factory) -> list[Task]:
    tasks = [
        task_factory(
            user_id=1,
            title="High Priority Pending",
            status=TaskStatus.PENDING.value,
            priority=TaskPriority.HIGH.value,
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
        ),
        task_factory(
            user_id=1,
            title="Medium Priority In Progress",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.MEDIUM.value,
        ),
        task_factory(
            user_id=1,
            title="Low Priority Completed",
            status=TaskStatus.COMPLETED.value,
            priority=TaskPriority.LOW.value,
        ),
        task_factory(
            user_id=1,
            title="High Priority In Progress",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.HIGH.value,
            due_date=datetime.now(timezone.utc) + timedelta(days=7),
        ),
    ]
    return tasks


@pytest.fixture
def valid_task_data() -> dict[str, Any]:
    return {
        "title": "Test Task",
        "description": "This is a test task description",
        "status": TaskStatus.PENDING.value,
        "priority": TaskPriority.MEDIUM.value,
        "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    }


@pytest.fixture
def minimal_task_data() -> dict[str, str]:
    return {"title": "Minimal Task"}

