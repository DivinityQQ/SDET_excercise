"""Test helper functions used across service test suites."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


DEFAULT_TEST_USER_ID = 1
DEFAULT_TEST_USERNAME = "test_user"

def _generate_rsa_key_pair() -> tuple[str, str]:
    """Generate an in-memory RSA private/public key pair as PEM strings."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


# Stable for one Python process: generated once on import, reused everywhere in tests.
TEST_PRIVATE_KEY, TEST_PUBLIC_KEY = _generate_rsa_key_pair()


def generate_throwaway_key_pair() -> tuple[str, str]:
    """Generate a fresh RSA key pair for negative-path tests."""
    return _generate_rsa_key_pair()


def create_test_token(
    user_id: int = DEFAULT_TEST_USER_ID,
    username: str = DEFAULT_TEST_USERNAME,
    private_key: str = TEST_PRIVATE_KEY,
    expired: bool = False,
) -> str:
    """Create a signed RS256 test token with required claims."""
    now = datetime.now(timezone.utc)
    expiry_time = now - timedelta(hours=1) if expired else now + timedelta(hours=1)

    payload: dict[str, Any] = {
        "user_id": int(user_id),
        "username": str(username),
        "iat": int(now.timestamp()),
        "exp": int(expiry_time.timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def auth_headers(token: str) -> dict[str, str]:
    """Build common JSON API headers with bearer token auth."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
