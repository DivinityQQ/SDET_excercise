"""Shared fixtures for the security test suite."""

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
    """Provide isolated task-service test client + DB lifecycle per test."""
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
    """Mint a valid RS256 token for a unique synthetic user identity."""

    def _token_for_user() -> tuple[str, dict]:
        user_id = next(_user_counter)
        username = f"security_user_{user_id}"
        token = create_test_token(
            user_id=user_id,
            username=username,
            private_key=TEST_PRIVATE_KEY,
        )
        return token, {"id": user_id, "username": username}

    return _token_for_user
