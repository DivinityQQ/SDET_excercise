"""Unit tests for auth User model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from auth_app.models import User

pytestmark = pytest.mark.unit


def test_set_password_hashes_plain_text(db_session):
    user = User(username="alice", email="alice@example.com")
    user.set_password("Secret123!")

    assert user.password_hash != "Secret123!"
    assert user.check_password("Secret123!")


def test_check_password_rejects_wrong_value(db_session):
    user = User(username="bob", email="bob@example.com")
    user.set_password("CorrectPass123!")

    assert user.check_password("WrongPass123!") is False


def test_to_dict_excludes_password_hash(db_session):
    user = User(username="carol", email="carol@example.com")
    user.set_password("Secret123!")
    db_session.session.add(user)
    db_session.session.commit()

    payload = user.to_dict()

    assert payload["username"] == "carol"
    assert payload["email"] == "carol@example.com"
    assert "password_hash" not in payload
    assert payload["created_at"] is not None


def test_unique_username_constraint(db_session, user_factory):
    user_factory(username="dupe", email="first@example.com")
    duplicate = User(username="dupe", email="second@example.com")
    duplicate.set_password("Secret123!")
    db_session.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.session.commit()
    db_session.session.rollback()


def test_unique_email_constraint(db_session, user_factory):
    user_factory(username="first", email="dupe@example.com")
    duplicate = User(username="second", email="dupe@example.com")
    duplicate.set_password("Secret123!")
    db_session.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.session.commit()
    db_session.session.rollback()
