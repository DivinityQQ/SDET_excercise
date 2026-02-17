"""
JWT verification helpers for the frontend service.

Provides a single ``verify_token`` function that decodes and validates JWTs
issued by the auth service.  The frontend only needs the *public* half of
the RS256 key-pair -- it never creates tokens, only verifies them -- which
means the auth service's private key stays isolated in its own deployment.

The function validates both the cryptographic signature and a set of
semantic checks (required claims, positive ``user_id``, non-blank
``username``) so that callers can trust the returned payload without
further defensive checks.

Key Concepts Demonstrated:
- RS256 asymmetric verification with PyJWT
- Required-claim enforcement via PyJWT ``options``
- Clock-skew tolerance (``leeway``) for distributed deployments
- Defensive post-decode validation of identity claims
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

    Verifies the RS256 signature, checks expiration, ensures all required
    claims are present, and performs semantic validation on the identity
    claims (``user_id`` must be a positive int, ``username`` must be
    non-blank).

    Args:
        token: The raw compact-JWS token string to verify.
        public_key: The RSA public key in PEM format used to verify the
            token signature.
        algorithms: Allowed signing algorithms.  Defaults to
            ``["RS256"]`` when *None*.

    Returns:
        The decoded payload dictionary on success, or ``None`` if the
        token is expired, malformed, has an invalid signature, or fails
        claim validation.
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

    # Post-decode semantic validation: ensure identity claims carry
    # sensible values even though the signature was valid.
    user_id = decoded.get("user_id")
    username = decoded.get("username")

    if not isinstance(user_id, int) or user_id <= 0:
        return None
    if not isinstance(username, str) or not username.strip():
        return None
    return decoded
