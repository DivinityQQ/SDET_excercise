"""
Integration tests for frontend-service HTML authentication and task views.

Exercises the frontend BFF routes (login, register, logout, task list)
through the Flask test client with monkeypatched HTTP calls to the
downstream auth and task services.  This approach verifies the full
request/response cycle (form submission, session management, redirects,
template rendering) without requiring live micro-services.

Key SDET Concepts Demonstrated:
- Integration testing through the full HTTP request/response cycle
- Monkeypatching external HTTP calls for isolated service testing
- Session-state assertions (token storage and cleanup)
- Redirect-chain verification for authentication flows
- Fake response objects as lightweight test doubles
"""

from __future__ import annotations

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, create_test_token

pytestmark = pytest.mark.integration


class _FakeResponse:
    """
    Minimal stand-in for :class:`requests.Response`.

    Provides just enough interface (``status_code`` and ``json()``) to
    satisfy the frontend route handlers, which only inspect these two
    attributes when processing downstream service replies.

    Attributes:
        status_code: HTTP status code returned by the fake response.
    """

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        """Return the pre-configured JSON payload."""
        return self._payload


def test_unauthenticated_user_redirected_to_login(client):
    """Test that accessing the root URL without a session token redirects to /login."""
    # Arrange -- no auth token is present in session

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_stores_token_in_session(client, monkeypatch):
    """Test that a successful login stores the JWT in session and redirects home."""
    # Arrange
    token = create_test_token(
        user_id=1,
        username="demo",
        private_key=TEST_PRIVATE_KEY,
    )
    monkeypatch.setattr(
        "frontend_app.routes.views.requests.post",
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


def test_register_success_redirects_to_login(client, monkeypatch):
    """Test that a successful registration redirects to /login."""
    # Arrange
    monkeypatch.setattr(
        "frontend_app.routes.views.requests.post",
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


def test_logout_clears_session(client):
    """Test that POST /logout removes auth_token from session and redirects to /login."""
    # Arrange
    with client.session_transaction() as sess:
        sess["auth_token"] = "token-to-clear"

    # Act
    response = client.post("/logout", follow_redirects=False)

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "auth_token" not in sess


def test_authenticated_index_fetches_tasks_from_task_api(client, monkeypatch):
    """Test that the authenticated index calls the task API and renders task titles."""
    # Arrange
    token = create_test_token(
        user_id=1,
        username="demo",
        private_key=TEST_PRIVATE_KEY,
    )
    with client.session_transaction() as sess:
        sess["auth_token"] = token

    def _fake_request(**kwargs):
        assert kwargs["method"] == "GET"
        assert "/api/tasks" in kwargs["url"]
        assert kwargs["headers"]["Authorization"] == f"Bearer {token}"
        return _FakeResponse(
            status_code=200,
            payload={
                "tasks": [
                    {
                        "id": 1,
                        "user_id": 1,
                        "title": "Task from API",
                        "description": None,
                        "status": "pending",
                        "priority": "medium",
                        "due_date": None,
                        "estimated_minutes": None,
                        "created_at": "2026-01-01T10:00:00+00:00",
                        "updated_at": "2026-01-01T10:00:00+00:00",
                    }
                ],
                "count": 1,
            },
        )

    monkeypatch.setattr("frontend_app.routes.views.requests.request", _fake_request)

    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 200
    assert b"Task from API" in response.data
