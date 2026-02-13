"""
JWT verification helpers for the frontend service.
"""

from __future__ import annotations

from typing import Any

import jwt
from flask import current_app

DEFAULT_ALLOWED_ALGORITHMS = ["RS256"]
REQUIRED_TOKEN_CLAIMS = ["user_id", "username", "iat", "exp"]


def verify_token(
    token: str,
    public_key: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Decode and validate a JWT, returning the payload on success.

    Returns None when verification fails.
    """
    try:
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=algorithms or DEFAULT_ALLOWED_ALGORITHMS,
            options={"require": REQUIRED_TOKEN_CLAIMS},
            leeway=int(current_app.config.get("JWT_CLOCK_SKEW_SECONDS", 30)),
        )
    except jwt.InvalidTokenError:
        return None

    user_id = decoded.get("user_id")
    username = decoded.get("username")

    if not isinstance(user_id, int) or user_id <= 0:
        return None
    if not isinstance(username, str) or not username.strip():
        return None
    return decoded
