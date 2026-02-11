"""Shared pytest fixtures for auth service tests."""

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
def user_factory(db_session) -> Callable[..., User]:
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

