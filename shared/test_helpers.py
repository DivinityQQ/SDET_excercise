"""Test helper functions used across service test suites."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


DEFAULT_TEST_USER_ID = 1
DEFAULT_TEST_USERNAME = "test_user"
DEFAULT_TEST_SECRET = "test-jwt-secret-key-for-local-tests-123456"


def create_test_token(
    user_id: int = DEFAULT_TEST_USER_ID,
    username: str = DEFAULT_TEST_USERNAME,
    secret: str = DEFAULT_TEST_SECRET,
    expired: bool = False,
) -> str:
    """Create a signed HS256 test token with required claims."""
    now = datetime.now(timezone.utc)
    expiry_time = now - timedelta(hours=1) if expired else now + timedelta(hours=1)

    payload: dict[str, Any] = {
        "user_id": int(user_id),
        "username": str(username),
        "iat": int(now.timestamp()),
        "exp": int(expiry_time.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_headers(token: str) -> dict[str, str]:
    """Build common JSON API headers with bearer token auth."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
