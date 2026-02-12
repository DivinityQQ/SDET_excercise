"""
Shared pytest fixtures for auth service tests.

Provides the reusable test infrastructure (Flask app, HTTP client,
database session, and a user factory) needed by unit, integration,
and contract test suites in this service.

Key SDET Concepts Demonstrated:
- Fixture scoping (session vs. function) for performance and isolation
- Factory-pattern fixtures for flexible test-data creation
- Automatic teardown / cleanup to prevent test pollution
- Environment variable overrides for deterministic test configuration
"""

from __future__ import annotations

import os
from collections.abc import Callable

import pytest

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_JWT_SECRET_KEY"] = "test-jwt-secret-key-for-local-tests-123456"

from auth_app import create_app, db
from auth_app.models import User


@pytest.fixture(scope="session")
def app():
    """
    Provide the Flask application instance for the entire test session.

    Creates the app once with the 'testing' config and reuses it
    across all tests to avoid repeated startup overhead.
    """
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """
    Provide a Flask test client scoped to a single test function.

    Opens a new test-client context for every test so that request
    state (cookies, sessions) never leaks between tests.
    """
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session(app):
    """
    Provide a clean database session for each test function.

    Creates all tables before the test runs, then rolls back any
    uncommitted changes and drops all tables afterward, ensuring
    complete isolation between tests.
    """
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def user_factory(db_session) -> Callable[..., User]:
    """
    Provide a factory function that creates and persists User records.

    Accepts optional username, email, and password arguments so each
    test can request users with specific attributes.  All created
    users are tracked and deleted during teardown to keep the
    database clean for the next test.
    """
    created_users: list[User] = []

    def _create_user(
        username: str = "testuser",
        email: str = "testuser@example.com",
        password: str = "StrongPass123!",
    ) -> User:
        user = User(username=username, email=email)
        user.set_password(password)
        db_session.session.add(user)
        db_session.session.commit()
        created_users.append(user)
        return user

    yield _create_user

    for user in created_users:
        user_id = getattr(user, "id", None)
        if not user_id:
            continue
        existing = db_session.session.get(User, user_id)
        if existing:
            db_session.session.delete(existing)
    db_session.session.commit()
