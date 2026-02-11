"""Integration tests for task-service HTML auth flow."""

from __future__ import annotations

import pytest

from shared.test_helpers import create_test_token

pytestmark = pytest.mark.integration


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_unauthenticated_user_redirected_to_login(client, db_session):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_stores_token_in_session(app, client, db_session, monkeypatch):
    token = create_test_token(
        user_id=1,
        username="demo",
        secret=app.config["JWT_SECRET_KEY"],
    )
    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
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


def test_register_success_redirects_to_login(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: _FakeResponse(status_code=201, payload={"user": {"id": 1}}),
    )
    response = client.post(
        "/register",
        data={"username": "new_user", "email": "new_user@example.com", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logout_clears_session(client, db_session):
    with client.session_transaction() as sess:
        sess["auth_token"] = "token-to-clear"

    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction() as sess:
        assert "auth_token" not in sess

