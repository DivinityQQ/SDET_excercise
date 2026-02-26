"""
Integration tests for auth API endpoints.

Exercises every public route exposed by the auth service
(/register, /login, /verify, /health) through the Flask test client,
verifying correct HTTP status codes, response bodies, and error handling
across a variety of valid and invalid inputs.

Key SDET Concepts Demonstrated:
- Integration testing through the full HTTP request/response cycle
- HTTP method coverage (POST for mutations, GET for reads)
- Status-code assertions (200, 201, 400, 401, 409)
- Parametrised tests for combinatorial input validation
- Fixture-based test-data setup for repeatable scenarios
"""

from __future__ import annotations

import pytest

from services.auth.auth_app.jwt import create_token

pytestmark = pytest.mark.integration


def _register_payload(
    username: str = "new_user", email: str = "new_user@example.com"
) -> dict[str, str]:
    """
    Build a valid registration request body with sensible defaults.

    Centralises payload construction so that tests only need to override
    the fields relevant to the scenario under test.
    """
    return {
        "username": username,
        "email": email,
        "password": "StrongPass123!",
    }


@pytest.mark.security
def test_register_user_success(client, db_session):
    """Test that a valid registration creates a user and returns 201."""
    # Arrange
    payload = _register_payload()

    # Act
    response = client.post("/api/auth/register", json=payload)

    # Assert
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
    """Test that omitting a required field returns 400 with an error message."""
    # Arrange - provided by parametrize (payload already defined)

    # Act
    response = client.post("/api/auth/register", json=payload)

    # Assert
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_duplicate_username_returns_409(client, db_session, user_factory):
    """Test that registering with an existing username returns 409."""
    # Arrange
    user_factory(username="taken", email="first@example.com")

    # Act
    response = client.post(
        "/api/auth/register",
        json=_register_payload(username="taken", email="second@example.com"),
    )

    # Assert
    assert response.status_code == 409
    assert response.get_json() == {"error": "Username already exists"}


def test_register_duplicate_email_returns_409(client, db_session, user_factory):
    """Test that registering with an existing email returns 409."""
    # Arrange
    user_factory(username="first", email="taken@example.com")

    # Act
    response = client.post(
        "/api/auth/register",
        json=_register_payload(username="second", email="taken@example.com"),
    )

    # Assert
    assert response.status_code == 409
    assert response.get_json() == {"error": "Email already exists"}


def test_login_success_returns_token_and_user(client, db_session, user_factory):
    """Test that valid credentials return 200 with a JWT and user data."""
    # Arrange
    user = user_factory(username="login_user", email="login@example.com", password="S3cret!")

    # Act
    response = client.post(
        "/api/auth/login",
        json={"username": "login_user", "password": "S3cret!"},
    )

    # Assert
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body["token"], str)
    assert body["user"]["id"] == user.id
    assert body["user"]["username"] == "login_user"


@pytest.mark.security
def test_login_wrong_password_returns_401(client, db_session, user_factory):
    """Test that an incorrect password returns 401 with a generic error."""
    # Arrange
    user_factory(username="login_user", email="login@example.com", password="S3cret!")

    # Act
    response = client.post(
        "/api/auth/login",
        json={"username": "login_user", "password": "wrong"},
    )

    # Assert
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid username or password"}


def test_verify_returns_user_data_for_valid_token(client, db_session, user_factory, app):
    """Test that /verify returns user info when given a valid Bearer token."""
    # Arrange
    user = user_factory(username="verify_user", email="verify@example.com")
    token = create_token(
        user_id=user.id,
        username=user.username,
        private_key=app.config["JWT_PRIVATE_KEY"],
        expiry_hours=1,
    )

    # Act
    response = client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 200
    assert response.get_json() == {"user_id": user.id, "username": "verify_user"}


@pytest.mark.security
def test_verify_missing_header_returns_401(client, db_session):
    """Test that /verify without an Authorization header returns 401."""
    # Arrange - (no setup needed)

    # Act
    response = client.get("/api/auth/verify")

    # Assert
    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


@pytest.mark.security
def test_verify_expired_token_returns_401(client, db_session, user_factory, app):
    """Test that /verify rejects an expired token with 401."""
    # Arrange
    user = user_factory(username="expired_user", email="expired@example.com")
    token = create_token(
        user_id=user.id,
        username=user.username,
        private_key=app.config["JWT_PRIVATE_KEY"],
        expiry_hours=-1,
    )

    # Act
    response = client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid or expired token"}


def test_health_endpoint_returns_200(client, db_session):
    """Test that the health endpoint reports the service as healthy."""
    # Arrange - (no setup needed)

    # Act
    response = client.get("/api/auth/health")

    # Assert
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "healthy"
    assert body["service"] == "auth"
