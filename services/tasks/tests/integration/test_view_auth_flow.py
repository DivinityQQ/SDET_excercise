"""
Integration tests for task-service HTML-based authentication flow.

Exercises the browser-facing login, register, and logout view routes by
monkeypatching the outbound ``requests.post`` call to the auth service
with a lightweight ``_FakeResponse`` stub. This isolates the task service
from the real auth service while still verifying redirect behaviour,
session-cookie storage, and session cleanup.

Key SDET Concepts Demonstrated:
- Monkeypatching external HTTP calls with a fake response object
- Session-level assertions (Flask session_transaction)
- Redirect-chain verification (302 + Location header)
- Stub / test-double pattern (_FakeResponse)
"""

from __future__ import annotations

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, create_test_token

pytestmark = pytest.mark.integration


class _FakeResponse:
    """
    Minimal stand-in for ``requests.Response``.

    Provides just enough interface (``status_code`` and ``json()``) for
    the view code under test to consume without hitting a real HTTP server.
    """

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_unauthenticated_user_redirected_to_login(client, db_session):
    """Test that accessing the root page without a session redirects to /login."""
    # Arrange - no session token set

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_stores_token_in_session(app, client, db_session, monkeypatch):
    """Test that a successful login stores the JWT in the Flask session and redirects home."""
    # Arrange — monkeypatch auth-service response to return a valid token
    token = create_test_token(
        user_id=1,
        username="demo",
        private_key=TEST_PRIVATE_KEY,
    )
    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: _FakeResponse(
            status_code=200,
            payload={"token": token, "user": {"id": 1, "username": "demo"}},
        ),
    )

    # Act
    response = client.post(
        "/login",
        data={"username": "demo", "password": "secret"},
        follow_redirects=False,
    )

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert sess.get("auth_token") == token


def test_register_success_redirects_to_login(client, db_session, monkeypatch):
    """Test that a successful registration redirects the user to the login page."""
    # Arrange — monkeypatch auth-service response to return 201 Created
    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: _FakeResponse(status_code=201, payload={"user": {"id": 1}}),
    )

    # Act
    response = client.post(
        "/register",
        data={"username": "new_user", "email": "new_user@example.com", "password": "secret"},
        follow_redirects=False,
    )

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logout_clears_session(client, db_session):
    """Test that POST /logout removes auth_token from the session and redirects to /login."""
    # Arrange — seed the session with a token
    with client.session_transaction() as sess:
        sess["auth_token"] = "token-to-clear"

    # Act
    response = client.post("/logout", follow_redirects=False)

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "auth_token" not in sess
