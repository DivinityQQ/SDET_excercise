"""
Unit tests for auth JWT token creation and validation.

Verifies that the ``create_token`` helper produces standards-compliant
RS256 JWTs with the expected claims, and that expiration / clock-skew
behaviour matches the project's security requirements.

Key SDET Concepts Demonstrated:
- Pure unit testing with no database or HTTP layer
- Positive and negative token-validation scenarios
- Boundary testing for time-sensitive logic (clock skew / leeway)
- Using pytest.raises for expected-exception assertions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from auth_app.jwt import create_token
from shared.test_helpers import TEST_PRIVATE_KEY, TEST_PUBLIC_KEY

pytestmark = pytest.mark.unit

def test_create_token_contains_required_claims():
    """Test that a newly created token embeds all mandatory JWT claims."""
    # Arrange
    user_id = 7
    username = "alice"

    # Act
    token = create_token(
        user_id=user_id,
        username=username,
        private_key=TEST_PRIVATE_KEY,
        expiry_hours=1,
    )

    payload = jwt.decode(
        token,
        TEST_PUBLIC_KEY,
        algorithms=["RS256"],
        options={"require": ["user_id", "username", "iat", "exp"]},
    )

    # Assert
    assert payload["user_id"] == 7
    assert payload["username"] == "alice"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_create_token_expired_fails_decode():
    """Test that decoding an already-expired token raises ExpiredSignatureError."""
    # Arrange
    token = create_token(
        user_id=1,
        username="alice",
        private_key=TEST_PRIVATE_KEY,
        expiry_hours=-1,
    )

    # Act & Assert
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, TEST_PUBLIC_KEY, algorithms=["RS256"])


def test_create_token_sets_rs256_header_only():
    """Test that the token header specifies RS256 as the signing algorithm."""
    # Arrange
    token = create_token(
        user_id=1,
        username="alice",
        private_key=TEST_PRIVATE_KEY,
        expiry_hours=1,
    )

    # Act
    header = jwt.get_unverified_header(token)

    # Assert
    assert header["alg"] == "RS256"


def test_clock_skew_within_tolerance_is_accepted():
    """Test that a token expired just within the leeway window is still accepted."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 1,
        "username": "alice",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=20)).timestamp()),
    }
    token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

    # Act
    decoded = jwt.decode(token, TEST_PUBLIC_KEY, algorithms=["RS256"], leeway=30)

    # Assert
    assert decoded["user_id"] == 1


def test_clock_skew_beyond_tolerance_is_rejected():
    """Test that a token expired beyond the leeway window is rejected."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 1,
        "username": "alice",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=45)).timestamp()),
    }
    token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

    # Act & Assert
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, TEST_PUBLIC_KEY, algorithms=["RS256"], leeway=30)
