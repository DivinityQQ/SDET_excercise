"""
Shared pytest fixtures for the Task Manager test suite.

This module contains fixtures that are shared across all test modules.
Fixtures follow the Arrange-Act-Assert (AAA) pattern and ensure
test isolation by providing fresh data for each test.

Key Concepts Demonstrated:
- Fixture scopes (function, module, session)
- Fixture dependencies
- Test data factories
- Database setup/teardown
- Test client creation
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any
from faker import Faker

# Set testing environment before importing app
os.environ["FLASK_ENV"] = "testing"

from app import create_app, db
from app.models import Task, TaskStatus, TaskPriority


# Initialize Faker for generating test data
fake = Faker()


# -----------------------------------------------------------------------------
# Application Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """
    Create application instance for the test session.

    This fixture creates a Flask app configured for testing.
    The 'session' scope means the same app instance is reused
    for all tests, improving performance.

    Yields:
        Flask application instance configured for testing.
    """
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """
    Create a test client for making HTTP requests.

    The test client allows you to make requests to the app
    without running a real server. This is faster and more
    reliable for testing.

    Args:
        app: Flask application fixture.

    Yields:
        Flask test client for making HTTP requests.
    """
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session(app):
    """
    Create a fresh database session for each test.

    This fixture ensures test isolation by:
    1. Creating all tables before the test
    2. Providing a clean database session
    3. Rolling back all changes after the test

    Args:
        app: Flask application fixture.

    Yields:
        SQLAlchemy database session.
    """
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()
        db.drop_all()


# -----------------------------------------------------------------------------
# Test Data Factory Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def task_factory(db_session):
    """
    Factory fixture for creating Task instances.

    This factory pattern allows tests to easily create tasks
    with default or custom values. It demonstrates the
    Factory pattern commonly used in testing.

    Args:
        db_session: Database session fixture.

    Returns:
        Function that creates and returns Task instances.

    Example:
        def test_something(task_factory):
            task = task_factory(title="My Task")
            assert task.id is not None
    """
    created_tasks = []

    def _create_task(
        title: str | None = None,
        description: str | None = None,
        status: str = TaskStatus.PENDING.value,
        priority: str = TaskPriority.MEDIUM.value,
        due_date: datetime | None = None
    ) -> Task:
        """
        Create a task with the given or default values.

        Args:
            title: Task title (defaults to random sentence).
            description: Task description (defaults to random paragraph).
            status: Task status (defaults to pending).
            priority: Task priority (defaults to medium).
            due_date: Task due date (defaults to None).

        Returns:
            Created Task instance with an ID.
        """
        task = Task(
            title=title or fake.sentence(nb_words=4),
            description=description or fake.paragraph(),
            status=status,
            priority=priority,
            due_date=due_date
        )
        db_session.session.add(task)
        db_session.session.commit()
        created_tasks.append(task)
        return task

    yield _create_task

    # Cleanup: Remove all created tasks after the test
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
    Create a single sample task for tests that need one task.

    This is a convenience fixture for tests that just need
    a single task without customization.

    Args:
        task_factory: Task factory fixture.

    Returns:
        A single Task instance.
    """
    return task_factory(
        title="Sample Task",
        description="This is a sample task for testing",
        status=TaskStatus.PENDING.value,
        priority=TaskPriority.MEDIUM.value
    )


@pytest.fixture
def multiple_tasks(task_factory) -> list[Task]:
    """
    Create multiple tasks with different statuses and priorities.

    This fixture is useful for testing filtering, sorting,
    and list operations.

    Args:
        task_factory: Task factory fixture.

    Returns:
        List of Task instances with varied properties.
    """
    tasks = [
        task_factory(
            title="High Priority Pending",
            status=TaskStatus.PENDING.value,
            priority=TaskPriority.HIGH.value,
            due_date=datetime.now(timezone.utc) + timedelta(days=1)
        ),
        task_factory(
            title="Medium Priority In Progress",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.MEDIUM.value
        ),
        task_factory(
            title="Low Priority Completed",
            status=TaskStatus.COMPLETED.value,
            priority=TaskPriority.LOW.value
        ),
        task_factory(
            title="High Priority In Progress",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.HIGH.value,
            due_date=datetime.now(timezone.utc) + timedelta(days=7)
        ),
    ]
    return tasks


# -----------------------------------------------------------------------------
# Test Data Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def valid_task_data() -> dict[str, Any]:
    """
    Provide valid task data for POST/PUT requests.

    Returns:
        Dictionary with valid task field values.
    """
    return {
        "title": "Test Task",
        "description": "This is a test task description",
        "status": TaskStatus.PENDING.value,
        "priority": TaskPriority.MEDIUM.value,
        "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    }


@pytest.fixture
def minimal_task_data() -> dict[str, str]:
    """
    Provide minimal valid task data (only required fields).

    Returns:
        Dictionary with only required fields.
    """
    return {"title": "Minimal Task"}


# -----------------------------------------------------------------------------
# API Helper Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def api_base_url() -> str:
    """
    Provide the base URL for API endpoints.

    Returns:
        Base URL string for API routes.
    """
    return "/api"


@pytest.fixture
def api_headers() -> dict[str, str]:
    """
    Provide common headers for API requests.

    Returns:
        Dictionary of HTTP headers.
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
