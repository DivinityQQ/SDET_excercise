"""
JWT token creation for the auth service.

Encapsulates the logic for issuing JSON Web Tokens (JWTs) that are used as
bearer credentials across the micro-services architecture.  Tokens are signed
with the RS256 (RSA-SHA256) asymmetric algorithm, meaning only the issuer
(this service) holds the private key while verifiers only need the public key.

Token structure (claims):
    - ``user_id``  -- integer primary key of the authenticated user.
    - ``username`` -- human-readable identifier, carried for convenience so
      downstream services can display it without a round-trip to the DB.
    - ``iat``      -- *issued-at* timestamp (UTC epoch seconds).
    - ``exp``      -- *expiration* timestamp (UTC epoch seconds).  After this
      moment the token is rejected by any compliant verifier.

Key Concepts Demonstrated:
- RS256 asymmetric signing with PyJWT
- Canonical JWT claims (iat, exp) and custom claims
- Input validation before token creation
- UTC-only timestamps to avoid timezone ambiguity
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def create_token(
    user_id: int,
    username: str,
    private_key: str,
    expiry_hours: int,
) -> str:
    """
    Create an RS256-signed JWT containing canonical auth claims.

    Builds a payload with the caller-supplied identity fields plus standard
    ``iat`` (issued-at) and ``exp`` (expiration) timestamps, then signs it
    using the provided private key.

    Args:
        user_id: Primary key of the authenticated user.  Must be a
            positive integer.
        username: Display name of the user.  Must be a non-empty string.
        private_key: The RSA private key in PEM format used to sign the
            token.
        expiry_hours: Number of hours from *now* until the token expires.

    Returns:
        A compact JWS string (``header.payload.signature``) suitable for
        use as a Bearer token in HTTP ``Authorization`` headers.

    Raises:
        ValueError: If *user_id* is not positive or *username* is blank.
    """
    # Guard against nonsensical identity values before they make it into a signed token
    if int(user_id) <= 0:
        raise ValueError("user_id must be a positive integer")
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a non-empty string")

    # Always use UTC so that tokens are unambiguous regardless of the server's
    # local timezone setting.
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=int(expiry_hours))

    payload: dict[str, Any] = {
        "user_id": int(user_id),
        "username": username,
        # Store timestamps as integer epoch seconds -- the JWT spec (RFC 7519)
        # defines NumericDate as seconds since 1970-01-01T00:00:00Z.
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")
