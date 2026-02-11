"""Fixtures for cross-service contract and flow tests."""

from __future__ import annotations

import os

import pytest

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_JWT_SECRET_KEY"] = "test-jwt-secret-key-for-local-tests-123456"

from services.auth.auth_app import create_app as create_auth_app
from services.auth.auth_app import db as auth_db
from services.tasks.task_app import create_app as create_task_app
from services.tasks.task_app import db as task_db


@pytest.fixture(scope="session")
def auth_service_app():
    return create_auth_app("testing")


@pytest.fixture(scope="session")
def task_service_app():
    return create_task_app("testing")


@pytest.fixture(scope="function")
def auth_client(auth_service_app):
    with auth_service_app.app_context():
        auth_db.create_all()
    with auth_service_app.test_client() as client:
        yield client
    with auth_service_app.app_context():
        auth_db.session.rollback()
        auth_db.drop_all()


@pytest.fixture(scope="function")
def task_client(task_service_app):
    with task_service_app.app_context():
        task_db.create_all()
    with task_service_app.test_client() as client:
        yield client
    with task_service_app.app_context():
        task_db.session.rollback()
        task_db.drop_all()


@pytest.fixture
def jwt_secret(auth_service_app) -> str:
    return auth_service_app.config["JWT_SECRET_KEY"]
