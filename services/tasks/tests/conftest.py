"""
Shared pytest fixtures for task-service tests.

Provides the Flask application, test client, database session, JWT tokens,
and reusable data factories used by unit, integration, contract, and
resilience test suites.

Key SDET Concepts Demonstrated:
- Session-scoped vs function-scoped fixtures for performance and isolation
- Factory pattern (task_factory) for flexible test-data creation
- Fixture teardown / cleanup to prevent test pollution
- Shared JWT token generation via the shared test-helpers library
"""

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
    """
    Provide the Flask application instance for the entire test session.

    Creates the app once using the 'testing' configuration and shares it
    across all tests so the application factory is not invoked repeatedly.
    """
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """
    Provide a Flask test client scoped to a single test function.

    A new test client is created for every test to ensure complete HTTP
    isolation between tests (cookies, sessions, etc.).
    """
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session(app):
    """
    Provide a clean database session for each test function.

    Creates all tables before the test, yields the db instance for use,
    then rolls back any uncommitted changes and drops all tables to
    guarantee a pristine state for the next test.
    """
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def test_token(app) -> str:
    """
    Generate a valid JWT token for user_id=1 ('user_one').

    Uses the shared test-helper so token format stays consistent across
    all services.
    """
    return create_test_token(
        user_id=1,
        username="user_one",
        secret=app.config["JWT_SECRET_KEY"],
    )


@pytest.fixture
def second_user_token(app) -> str:
    """
    Generate a valid JWT token for user_id=2 ('user_two').

    Used in tenant-isolation tests to verify that one user cannot access
    another user's tasks.
    """
    return create_test_token(
        user_id=2,
        username="user_two",
        secret=app.config["JWT_SECRET_KEY"],
    )


@pytest.fixture
def api_headers(test_token) -> dict[str, str]:
    """
    Build HTTP headers (Authorization + Content-Type) for user_one.

    Combines the Bearer token with the JSON content-type header so tests
    can pass a single ``headers`` dict to the test client.
    """
    return auth_headers(test_token)


@pytest.fixture
def second_user_headers(second_user_token) -> dict[str, str]:
    """
    Build HTTP headers (Authorization + Content-Type) for user_two.

    Mirror of ``api_headers`` but for the second user, enabling
    cross-user / tenant-isolation assertions.
    """
    return auth_headers(second_user_token)


@pytest.fixture
def task_factory(db_session):
    """
    Factory fixture that creates Task rows in the test database.

    Returns a callable ``_create_task(**kwargs)`` that inserts a task with
    sensible defaults (generated via Faker) and commits it.  All created
    tasks are tracked and cleaned up after the test finishes to avoid
    leaking state between tests.
    """
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
    """
    Create a single pre-built task owned by user_id=1.

    Useful when a test only needs one task with known, predictable values
    to assert against.
    """
    return task_factory(
        user_id=1,
        title="Sample Task",
        description="This is a sample task for testing",
        status=TaskStatus.PENDING.value,
        priority=TaskPriority.MEDIUM.value,
    )


@pytest.fixture
def multiple_tasks(task_factory) -> list[Task]:
    """
    Create a varied set of four tasks for user_id=1.

    Covers different combinations of status, priority, and due-date so
    filter and listing tests can verify correct behaviour without
    additional setup inside each test.
    """
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
    """
    Provide a complete, valid task payload dictionary.

    Includes every optional field so tests that need a fully-populated
    request body can use it directly.
    """
    return {
        "title": "Test Task",
        "description": "This is a test task description",
        "status": TaskStatus.PENDING.value,
        "priority": TaskPriority.MEDIUM.value,
        "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    }


@pytest.fixture
def minimal_task_data() -> dict[str, str]:
    """
    Provide the smallest valid task payload (title only).

    Used to verify that the API applies correct defaults when optional
    fields are omitted.
    """
    return {"title": "Minimal Task"}
