"""
Shared fixtures for the security test suite.

Provides session-scoped Flask application instances for the task and
frontend services, function-scoped test clients with full database
lifecycle management, and a factory fixture that mints unique JWT tokens
for each test.  The function-scoped client fixtures guarantee that every
test starts with a clean database, preventing cross-test pollution.

Key SDET Concepts Demonstrated:
- Session-scoped app creation for performance (one app per test run)
- Function-scoped clients for per-test database isolation
- Factory fixture pattern (``token_for_user``) for on-demand identity creation
- Monotonic user-ID counter to avoid collisions across tests
"""

from __future__ import annotations

import itertools
import os

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, TEST_PUBLIC_KEY, create_test_token

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_JWT_PUBLIC_KEY"] = TEST_PUBLIC_KEY

from services.frontend.frontend_app import create_app as create_frontend_app
from services.tasks.task_app import create_app as create_task_app
from services.tasks.task_app import db as task_db


_user_counter = itertools.count(1000)


@pytest.fixture(scope="session")
def task_service_app():
    """Provide a session-scoped task app for security tests."""
    return create_task_app("testing")


@pytest.fixture(scope="session")
def frontend_service_app():
    """Provide a session-scoped frontend app for security tests."""
    return create_frontend_app("testing")


@pytest.fixture(scope="function")
def task_client(task_service_app):
    """Provide isolated task-service test client with per-test DB lifecycle.

    Creates all tables before yielding the client and tears them down
    after the test completes, ensuring full isolation between tests.
    """
    with task_service_app.app_context():
        task_db.create_all()
    with task_service_app.test_client() as client:
        yield client
    with task_service_app.app_context():
        task_db.session.rollback()
        task_db.drop_all()


@pytest.fixture(scope="function")
def frontend_client(frontend_service_app):
    """Provide an isolated frontend test client per test."""
    with frontend_service_app.test_client() as client:
        yield client


@pytest.fixture
def token_for_user():
    """Return a factory that mints a valid RS256 token for a unique user.

    Each call to the returned callable increments a monotonic counter so
    that every test (and every user within a test) receives a distinct
    ``user_id``, preventing cross-test identity collisions.
    """

    def _factory() -> tuple[str, dict]:
        user_id = next(_user_counter)
        username = f"security_user_{user_id}"
        token = create_test_token(
            user_id=user_id,
            username=username,
            private_key=TEST_PRIVATE_KEY,
        )
        return token, {"id": user_id, "username": username}

    return _factory
