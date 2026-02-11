"""Database models for the auth service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(db.Model):
    """User model for authentication and identity."""

    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("length(username) <= 80", name="ck_users_username_len"),
        db.CheckConstraint("length(email) <= 120", name="ck_users_email_len"),
        db.CheckConstraint(
            "length(password_hash) <= 256", name="ck_users_password_hash_len"
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email: str = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def _to_utc_iso(value: datetime) -> str:
        """Serialize datetime to ISO-8601 UTC string."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()

    def set_password(self, password: str) -> None:
        """Hash and store user password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict[str, Any]:
        """Return user-safe representation without password hash."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self._to_utc_iso(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<User {self.id}: {self.username}>"
