"""JWT verification helpers for task service."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import jwt
from flask import Response, current_app, g, jsonify, request

DEFAULT_ALLOWED_ALGORITHMS = ["HS256"]
REQUIRED_TOKEN_CLAIMS = ["user_id", "username", "iat", "exp"]


def verify_token(
    token: str,
    secret: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any] | None:
    """Verify token and return payload if valid, otherwise None."""
    try:
        decoded = jwt.decode(
            token,
            secret,
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


def require_auth(view_func: Callable[..., tuple[Response, int] | Response]):
    """Require valid bearer token and populate flask.g identity."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:].strip()
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        payload = verify_token(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=DEFAULT_ALLOWED_ALGORITHMS,
        )
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = payload["user_id"]
        g.username = payload["username"]
        return view_func(*args, **kwargs)

    return wrapper

