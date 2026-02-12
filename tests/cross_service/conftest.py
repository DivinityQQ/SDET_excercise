"""
Cross-Service Test Fixtures for Microservices Integration Testing.

This module provides shared pytest fixtures that spin up multiple Flask
applications (auth and tasks) in the same process so that cross-service
interactions can be tested without Docker or HTTP networking.  Each
service gets its own test client and its own in-memory database, just
like production where each microservice owns its datastore independently.

Key SDET Concepts Demonstrated:
- Session-scoped app fixtures to avoid repeated startup costs
- Function-scoped test clients for per-test database isolation
- Shared RSA key fixtures so auth and task services agree on JWT contract
- Teardown patterns (rollback + drop_all) to prevent test pollution
"""

from __future__ import annotations

import os

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, TEST_PUBLIC_KEY

os.environ["FLASK_ENV"] = "testing"
# Cross-service tests boot both apps: auth needs private+public, task uses public.
os.environ["TEST_JWT_PRIVATE_KEY"] = TEST_PRIVATE_KEY
os.environ["TEST_JWT_PUBLIC_KEY"] = TEST_PUBLIC_KEY

from services.auth.auth_app import create_app as create_auth_app
from services.auth.auth_app import db as auth_db
from services.tasks.task_app import create_app as create_task_app
from services.tasks.task_app import db as task_db


@pytest.fixture(scope="session")
def auth_service_app():
    """Provide a session-scoped auth Flask app for cross-service tests."""
    return create_auth_app("testing")


@pytest.fixture(scope="session")
def task_service_app():
    """Provide a session-scoped task Flask app for cross-service tests."""
    return create_task_app("testing")


@pytest.fixture(scope="function")
def auth_client(auth_service_app):
    """Provide a per-test auth service client with fresh database tables."""
    with auth_service_app.app_context():
        auth_db.create_all()
    with auth_service_app.test_client() as client:
        yield client
    with auth_service_app.app_context():
        auth_db.session.rollback()
        auth_db.drop_all()


@pytest.fixture(scope="function")
def task_client(task_service_app):
    """Provide a per-test task service client with fresh database tables."""
    with task_service_app.app_context():
        task_db.create_all()
    with task_service_app.test_client() as client:
        yield client
    with task_service_app.app_context():
        task_db.session.rollback()
        task_db.drop_all()


@pytest.fixture
def jwt_private_key(auth_service_app) -> str:
    """Provide the JWT private key used by the auth service in tests."""
    return auth_service_app.config["JWT_PRIVATE_KEY"]


@pytest.fixture
def jwt_public_key(auth_service_app) -> str:
    """Provide the JWT public key shared with the task service in tests."""
    return auth_service_app.config["JWT_PUBLIC_KEY"]
