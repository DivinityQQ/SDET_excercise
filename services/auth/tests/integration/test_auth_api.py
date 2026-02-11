"""Integration tests for auth API endpoints."""

from __future__ import annotations

import pytest

from auth_app.jwt import create_token

pytestmark = pytest.mark.integration


def _register_payload(
    username: str = "new_user", email: str = "new_user@example.com"
) -> dict[str, str]:
    return {
        "username": username,
        "email": email,
        "password": "StrongPass123!",
    }


def test_register_user_success(client, db_session):
    response = client.post("/api/auth/register", json=_register_payload())

    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["username"] == "new_user"
    assert body["user"]["email"] == "new_user@example.com"
    assert "password_hash" not in body["user"]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a@example.com", "password": "StrongPass123!"},
        {"username": "alice", "password": "StrongPass123!"},
        {"username": "alice", "email": "a@example.com"},
    ],
)
def test_register_missing_fields_returns_400(client, db_session, payload):
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_duplicate_username_returns_409(client, db_session, user_factory):
    user_factory(username="taken", email="first@example.com")

    response = client.post(
        "/api/auth/register",
        json=_register_payload(username="taken", email="second@example.com"),
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "Username already exists"}


def test_register_duplicate_email_returns_409(client, db_session, user_factory):
    user_factory(username="first", email="taken@example.com")

    response = client.post(
        "/api/auth/register",
        json=_register_payload(username="second", email="taken@example.com"),
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "Email already exists"}


def test_login_success_returns_token_and_user(client, db_session, user_factory):
    user = user_factory(username="login_user", email="login@example.com", password="S3cret!")

    response = client.post(
        "/api/auth/login",
        json={"username": "login_user", "password": "S3cret!"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body["token"], str)
    assert body["user"]["id"] == user.id
    assert body["user"]["username"] == "login_user"


def test_login_wrong_password_returns_401(client, db_session, user_factory):
    user_factory(username="login_user", email="login@example.com", password="S3cret!")

    response = client.post(
        "/api/auth/login",
        json={"username": "login_user", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid username or password"}


def test_verify_returns_user_data_for_valid_token(client, db_session, user_factory, app):
    user = user_factory(username="verify_user", email="verify@example.com")
    token = create_token(
        user_id=user.id,
        username=user.username,
        secret=app.config["JWT_SECRET_KEY"],
        expiry_hours=1,
    )

    response = client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"user_id": user.id, "username": "verify_user"}


def test_verify_missing_header_returns_401(client, db_session):
    response = client.get("/api/auth/verify")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


def test_verify_expired_token_returns_401(client, db_session, user_factory, app):
    user = user_factory(username="expired_user", email="expired@example.com")
    token = create_token(
        user_id=user.id,
        username=user.username,
        secret=app.config["JWT_SECRET_KEY"],
        expiry_hours=-1,
    )

    response = client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid or expired token"}


def test_health_endpoint_returns_200(client, db_session):
    response = client.get("/api/auth/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "healthy"
    assert body["service"] == "auth"

