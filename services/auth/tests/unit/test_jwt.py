"""Unit tests for auth JWT creation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from auth_app.jwt import create_token

pytestmark = pytest.mark.unit

TEST_SECRET = "test-jwt-secret-key-for-local-tests-123456"


def test_create_token_contains_required_claims():
    token = create_token(
        user_id=7,
        username="alice",
        secret=TEST_SECRET,
        expiry_hours=1,
    )

    payload = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=["HS256"],
        options={"require": ["user_id", "username", "iat", "exp"]},
    )

    assert payload["user_id"] == 7
    assert payload["username"] == "alice"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_create_token_expired_fails_decode():
    token = create_token(
        user_id=1,
        username="alice",
        secret=TEST_SECRET,
        expiry_hours=-1,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, TEST_SECRET, algorithms=["HS256"])


def test_create_token_sets_hs256_header_only():
    token = create_token(
        user_id=1,
        username="alice",
        secret=TEST_SECRET,
        expiry_hours=1,
    )
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"


def test_clock_skew_within_tolerance_is_accepted():
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 1,
        "username": "alice",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=20)).timestamp()),
    }
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")

    decoded = jwt.decode(token, TEST_SECRET, algorithms=["HS256"], leeway=30)
    assert decoded["user_id"] == 1


def test_clock_skew_beyond_tolerance_is_rejected():
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 1,
        "username": "alice",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=45)).timestamp()),
    }
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, TEST_SECRET, algorithms=["HS256"], leeway=30)

