"""
Unit tests for the auth User model.

Exercises the User ORM model in isolation to verify password hashing,
safe serialisation, and database-level uniqueness constraints.

Key SDET Concepts Demonstrated:
- Testing model behaviour independently from HTTP/API layers
- Verifying security properties (password never stored in plain text)
- Asserting database constraints via expected IntegrityError exceptions
- Using factory fixtures for reusable test-data creation
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from auth_app.models import User

pytestmark = pytest.mark.unit


def test_set_password_hashes_plain_text(db_session):
    """Test that set_password stores a hash, not the original plain text."""
    # Arrange
    user = User(username="alice", email="alice@example.com")

    # Act
    user.set_password("Secret123!")

    # Assert
    assert user.password_hash != "Secret123!"
    assert user.check_password("Secret123!")


def test_check_password_rejects_wrong_value(db_session):
    """Test that check_password returns False for an incorrect password."""
    # Arrange
    user = User(username="bob", email="bob@example.com")
    user.set_password("CorrectPass123!")

    # Act
    result = user.check_password("WrongPass123!")

    # Assert
    assert result is False


def test_to_dict_excludes_password_hash(db_session):
    """Test that to_dict never exposes the password_hash field."""
    # Arrange
    user = User(username="carol", email="carol@example.com")
    user.set_password("Secret123!")
    db_session.session.add(user)
    db_session.session.commit()

    # Act
    payload = user.to_dict()

    # Assert
    assert payload["username"] == "carol"
    assert payload["email"] == "carol@example.com"
    assert "password_hash" not in payload
    assert payload["created_at"] is not None


def test_unique_username_constraint(db_session, user_factory):
    """Test that the database rejects a duplicate username."""
    # Arrange
    user_factory(username="dupe", email="first@example.com")
    duplicate = User(username="dupe", email="second@example.com")
    duplicate.set_password("Secret123!")
    db_session.session.add(duplicate)

    # Act & Assert
    with pytest.raises(IntegrityError):
        db_session.session.commit()
    db_session.session.rollback()


def test_unique_email_constraint(db_session, user_factory):
    """Test that the database rejects a duplicate email address."""
    # Arrange
    user_factory(username="first", email="dupe@example.com")
    duplicate = User(username="second", email="dupe@example.com")
    duplicate.set_password("Secret123!")
    db_session.session.add(duplicate)

    # Act & Assert
    with pytest.raises(IntegrityError):
        db_session.session.commit()
    db_session.session.rollback()
