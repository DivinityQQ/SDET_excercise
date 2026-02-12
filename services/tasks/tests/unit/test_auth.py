"""
Unit tests for task-service JWT verification and the ``require_auth`` decorator.

Exercises ``verify_token()`` against a comprehensive set of valid and invalid
tokens (expired, malformed, wrong secret, wrong algorithm, missing claims,
clock-skew edge cases) and verifies that the ``@require_auth`` route
decorator correctly gates access.

Key SDET Concepts Demonstrated:
- Boundary testing on token expiry and clock-skew tolerance
- Negative testing for malformed / tampered tokens
- Algorithm-confusion attack prevention (none, HS512)
- Required-claim validation (user_id, exp)
- Decorator integration with Flask request context
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from flask import Flask, jsonify, g

from task_app.auth import require_auth, verify_token

pytestmark = pytest.mark.unit

TEST_SECRET = "test-jwt-secret-key-for-local-tests-123456"


def _make_token(payload: dict, secret: str = TEST_SECRET, algorithm: str = "HS256") -> str:
    """Encode a JWT payload with the given secret and algorithm."""
    return jwt.encode(payload, secret, algorithm=algorithm)


def _required_claims(*, user_id: int = 1, username: str = "user_one") -> dict:
    """Build a valid claim set with sensible defaults and a 1-hour expiry."""
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }


def test_verify_token_valid_payload(app):
    """Test that a correctly signed, non-expired token returns its payload."""
    # Arrange
    token = _make_token(_required_claims())

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is not None
    assert payload["user_id"] == 1


def test_verify_token_expired_returns_none(app):
    """Test that a token whose exp is in the past is rejected."""
    # Arrange
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        }
    )

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_malformed_returns_none(app):
    """Test that a non-JWT string is safely rejected."""
    # Arrange - token is an arbitrary non-JWT string

    # Act
    with app.app_context():
        payload = verify_token("not-a-jwt", TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_wrong_secret_returns_none(app):
    """Test that a token signed with a different secret is rejected."""
    # Arrange
    token = _make_token(_required_claims(), secret="different-secret-key-for-tests-1234567890")

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_wrong_algorithm_none_rejected(app):
    """Test that tokens using the 'none' algorithm are rejected (algorithm-confusion attack)."""
    # Arrange
    token = _make_token(_required_claims(), secret="", algorithm="none")

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_wrong_algorithm_hs512_rejected(app):
    """Test that a token signed with HS512 is rejected when only HS256 is allowed."""
    # Arrange
    token = _make_token(
        _required_claims(),
        secret="h" * 64,
        algorithm="HS512",
    )

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_missing_user_id_claim_rejected(app):
    """Test that a token without the required 'user_id' claim is rejected."""
    # Arrange
    claims = _required_claims()
    claims.pop("user_id")
    token = _make_token(claims)

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_missing_exp_claim_rejected(app):
    """Test that a token without the required 'exp' claim is rejected."""
    # Arrange
    claims = _required_claims()
    claims.pop("exp")
    token = _make_token(claims)

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_verify_token_clock_skew_within_tolerance_accepted(app):
    """Test that a token expired by only ~20 seconds is accepted (within leeway)."""
    # Arrange
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(minutes=1)).timestamp()),
            "exp": int((now - timedelta(seconds=20)).timestamp()),
        }
    )

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is not None


def test_verify_token_clock_skew_beyond_tolerance_rejected(app):
    """Test that a token expired well beyond the leeway window is rejected."""
    # Arrange
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(minutes=2)).timestamp()),
            "exp": int((now - timedelta(seconds=45)).timestamp()),
        }
    )

    # Act
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    # Assert
    assert payload is None


def test_require_auth_decorator_rejects_missing_header():
    """Test that @require_auth returns 401 when no Authorization header is present."""
    # Arrange
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = TEST_SECRET

    @app.route("/_protected_test")
    @require_auth
    def _protected_test():
        return jsonify({"user_id": g.user_id})

    client = app.test_client()

    # Act
    response = client.get("/_protected_test")

    # Assert
    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


def test_require_auth_decorator_allows_valid_token():
    """Test that @require_auth passes through and populates g for a valid token."""
    # Arrange
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = TEST_SECRET

    @app.route("/_protected_test_2")
    @require_auth
    def _protected_test_2():
        return jsonify({"user_id": g.user_id, "username": g.username})

    client = app.test_client()
    token = _make_token(_required_claims(user_id=77, username="authorized_user"))

    # Act
    response = client.get(
        "/_protected_test_2",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 200
    assert response.get_json() == {"user_id": 77, "username": "authorized_user"}
