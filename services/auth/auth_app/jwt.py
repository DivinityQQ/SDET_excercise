"""JWT token creation for auth service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def create_token(
    user_id: int,
    username: str,
    secret: str,
    expiry_hours: int,
) -> str:
    """Create HS256 JWT with canonical auth claims."""
    if int(user_id) <= 0:
        raise ValueError("user_id must be a positive integer")
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a non-empty string")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=int(expiry_hours))

    payload: dict[str, Any] = {
        "user_id": int(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

