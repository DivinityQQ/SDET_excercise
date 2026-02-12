"""
JWT Verification Helpers for the Task Service.

Provides utilities for verifying JSON Web Tokens (JWTs) issued by the
auth service and a decorator for protecting Flask endpoints that require
authentication.  The task service never *issues* tokens -- it only
validates them using the auth service's ``JWT_PUBLIC_KEY``.

Key Concepts Demonstrated:
- JWT verification with the ``PyJWT`` library
- Decorator pattern for endpoint authentication (``require_auth``)
- Using ``flask.g`` to store request-scoped user identity
- Asymmetric verification of auth-issued tokens (RS256)
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import jwt
from flask import Response, current_app, g, jsonify, request

DEFAULT_ALLOWED_ALGORITHMS = ["RS256"]
REQUIRED_TOKEN_CLAIMS = ["user_id", "username", "iat", "exp"]


def verify_token(
    token: str,
    public_key: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Decode and validate a JWT, returning the payload on success.

    Performs full verification: signature check, expiry (``exp``), issued-at
    (``iat``), and presence of all required claims.  Additionally validates
    that ``user_id`` is a positive integer and ``username`` is a non-empty
    string.

    Args:
        token: The encoded JWT string to verify.
        public_key: The RSA public key in PEM format used for signature
            verification.
        algorithms: List of acceptable signing algorithms.  Defaults to
            ``["RS256"]`` to prevent algorithm-confusion attacks.

    Returns:
        The decoded payload dictionary if the token is valid, or ``None``
        if verification fails for any reason.
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
        # Return None rather than raising so callers can handle auth failure
        # with a simple ``if payload is None`` check instead of try/except.
        return None

    user_id = decoded.get("user_id")
    username = decoded.get("username")

    if not isinstance(user_id, int) or user_id <= 0:
        return None
    if not isinstance(username, str) or not username.strip():
        return None
    return decoded


def require_auth(view_func: Callable[..., tuple[Response, int] | Response]):
    """
    Decorator that enforces Bearer-token authentication on API endpoints.

    Extracts the ``Authorization: Bearer <token>`` header, verifies the JWT
    via ``verify_token``, and -- on success -- stores the authenticated
    user's identity in ``flask.g`` so that downstream route handlers can
    access ``g.user_id`` and ``g.username`` without re-parsing the token.

    If verification fails, the request is short-circuited with a ``401``
    JSON error response before the wrapped view function is invoked.

    Args:
        view_func: The Flask view function to protect.

    Returns:
        A wrapped view function that only executes when a valid JWT is
        present in the request headers.
    """

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
            current_app.config["JWT_PUBLIC_KEY"],
            algorithms=DEFAULT_ALLOWED_ALGORITHMS,
        )
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store user identity on flask.g -- a per-request namespace that is
        # automatically torn down at the end of the request.  This makes
        # user_id and username available to all downstream code without
        # passing them explicitly through function arguments.
        g.user_id = payload["user_id"]
        g.username = payload["username"]
        return view_func(*args, **kwargs)

    return wrapper
