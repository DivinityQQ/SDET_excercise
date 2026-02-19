"""
Database models for the auth service.

Defines the SQLAlchemy ORM models that back the authentication service.
Currently the only model is :class:`User`, which stores credentials and
profile data needed for registration, login, and JWT issuance.

Key Concepts Demonstrated:
- SQLAlchemy declarative model with explicit table constraints
- Werkzeug password hashing (PBKDF2 by default)
- Safe serialisation that excludes sensitive fields
- Timezone-aware datetime handling for SQLite compatibility
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(db.Model):
    """
    User model for authentication and identity.

    Represents a registered user of the system.  Passwords are never stored
    in plain text -- only a one-way hash is persisted.  The ``to_dict``
    helper deliberately omits ``password_hash`` so it can be safely
    returned in API responses.

    Attributes:
        id: Auto-incrementing integer primary key.
        username: Unique display name (max 80 chars).  Indexed for fast
            login lookups.
        email: Unique email address (max 120 chars).  Indexed so that
            duplicate-email checks during registration are efficient.
        password_hash: Werkzeug-generated hash of the user's password.
        created_at: Timestamp of account creation, stored as UTC.
    """

    __tablename__ = "users"

    # Database-level CHECK constraints provide a safety net that enforces
    # maximum lengths even if application-level validation is bypassed
    # (e.g. via a raw SQL session or future bulk-import script).
    __table_args__ = (
        db.CheckConstraint("length(username) <= 80", name="ck_users_username_len"),
        db.CheckConstraint("length(email) <= 120", name="ck_users_email_len"),
        db.CheckConstraint(
            "length(password_hash) <= 256", name="ck_users_password_hash_len"
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    # Indexed because every login request looks up a user by username
    username: str = db.Column(db.String(80), unique=True, nullable=False, index=True)
    # Indexed because registration checks for duplicate emails
    email: str = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def _to_utc_iso(value: datetime) -> str:
        """
        Serialize a datetime to an ISO-8601 UTC string.

        SQLite does not store timezone information, so datetimes read back
        from the database may be *naive* (``tzinfo is None``) even though
        they were originally created with ``timezone.utc``.  This helper
        normalises both cases: naive values are assumed to be UTC, and
        aware values are explicitly converted to UTC before formatting.
        This guarantees that every API response contains an unambiguous
        timezone-qualified timestamp.

        Args:
            value: The datetime to serialize.

        Returns:
            An ISO-8601 formatted string with a UTC timezone designator
            (e.g. ``"2025-01-15T08:30:00+00:00"``).
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()

    def set_password(self, password: str) -> None:
        """
        Hash and store a plain-text password.

        Uses Werkzeug's ``generate_password_hash`` which defaults to
        PBKDF2-SHA256 with a random salt.

        Args:
            password: The plain-text password to hash.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verify a plain-text password against the stored hash.

        Args:
            password: The candidate plain-text password.

        Returns:
            ``True`` if the password matches, ``False`` otherwise.
        """
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict[str, Any]:
        """
        Return a user-safe dictionary representation.

        The ``password_hash`` field is intentionally excluded so this
        output can be returned directly in JSON API responses without
        leaking sensitive data.

        Returns:
            A dict containing ``id``, ``username``, ``email``, and
            ``created_at`` (as an ISO-8601 UTC string).
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self._to_utc_iso(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<User {self.id}: {self.username}>"
