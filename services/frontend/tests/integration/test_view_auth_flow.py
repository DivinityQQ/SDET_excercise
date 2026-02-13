"""
Integration tests for frontend-service HTML authentication and task views.
"""

from __future__ import annotations

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, create_test_token

pytestmark = pytest.mark.integration


class _FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_unauthenticated_user_redirected_to_login(client):
    """Accessing root without session redirects to /login."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_stores_token_in_session(client, monkeypatch):
    """Successful login stores JWT in session and redirects home."""
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

    response = client.post(
        "/login",
        data={"username": "demo", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert sess.get("auth_token") == token


def test_register_success_redirects_to_login(client, monkeypatch):
    """Successful registration redirects to /login."""
    monkeypatch.setattr(
        "frontend_app.routes.views.requests.post",
        lambda *_, **__: _FakeResponse(status_code=201, payload={"user": {"id": 1}}),
    )

    response = client.post(
        "/register",
        data={"username": "new_user", "email": "new_user@example.com", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logout_clears_session(client):
    """POST /logout removes auth_token from session and redirects /login."""
    with client.session_transaction() as sess:
        sess["auth_token"] = "token-to-clear"

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "auth_token" not in sess


def test_authenticated_index_fetches_tasks_from_task_api(client, monkeypatch):
    """Authenticated index should call task API and render task title."""
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

    response = client.get("/")
    assert response.status_code == 200
    assert b"Task from API" in response.data
