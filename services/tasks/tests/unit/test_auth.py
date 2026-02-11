"""Unit tests for task service token verification and auth decorator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from flask import Flask, jsonify, g

from task_app.auth import require_auth, verify_token

pytestmark = pytest.mark.unit

TEST_SECRET = "test-jwt-secret-key-for-local-tests-123456"


def _make_token(payload: dict, secret: str = TEST_SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _required_claims(*, user_id: int = 1, username: str = "user_one") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }


def test_verify_token_valid_payload(app):
    token = _make_token(_required_claims())
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is not None
    assert payload["user_id"] == 1


def test_verify_token_expired_returns_none(app):
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        }
    )
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_malformed_returns_none(app):
    with app.app_context():
        payload = verify_token("not-a-jwt", TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_wrong_secret_returns_none(app):
    token = _make_token(_required_claims(), secret="different-secret-key-for-tests-1234567890")
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_wrong_algorithm_none_rejected(app):
    token = _make_token(_required_claims(), secret="", algorithm="none")
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_wrong_algorithm_hs512_rejected(app):
    token = _make_token(
        _required_claims(),
        secret="h" * 64,
        algorithm="HS512",
    )
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_missing_user_id_claim_rejected(app):
    claims = _required_claims()
    claims.pop("user_id")
    token = _make_token(claims)

    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_missing_exp_claim_rejected(app):
    claims = _required_claims()
    claims.pop("exp")
    token = _make_token(claims)

    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_verify_token_clock_skew_within_tolerance_accepted(app):
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(minutes=1)).timestamp()),
            "exp": int((now - timedelta(seconds=20)).timestamp()),
        }
    )
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is not None


def test_verify_token_clock_skew_beyond_tolerance_rejected(app):
    now = datetime.now(timezone.utc)
    token = _make_token(
        {
            "user_id": 1,
            "username": "user_one",
            "iat": int((now - timedelta(minutes=2)).timestamp()),
            "exp": int((now - timedelta(seconds=45)).timestamp()),
        }
    )
    with app.app_context():
        payload = verify_token(token, TEST_SECRET, algorithms=["HS256"])

    assert payload is None


def test_require_auth_decorator_rejects_missing_header():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = TEST_SECRET

    @app.route("/_protected_test")
    @require_auth
    def _protected_test():
        return jsonify({"user_id": g.user_id})

    client = app.test_client()
    response = client.get("/_protected_test")
    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


def test_require_auth_decorator_allows_valid_token():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = TEST_SECRET

    @app.route("/_protected_test_2")
    @require_auth
    def _protected_test_2():
        return jsonify({"user_id": g.user_id, "username": g.username})

    client = app.test_client()
    token = _make_token(_required_claims(user_id=77, username="authorized_user"))
    response = client.get(
        "/_protected_test_2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"user_id": 77, "username": "authorized_user"}
