"""Integration tests for gateway proxy behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration


class _FakeRawHeaders:
    def __init__(self, set_cookies: list[str] | None = None):
        self._set_cookies = set_cookies or []

    def getlist(self, name: str) -> list[str]:
        if name.lower() == "set-cookie":
            return self._set_cookies
        return []


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b'{"ok": true}',
        headers: dict[str, str] | None = None,
        set_cookies: list[str] | None = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}
        self.raw = SimpleNamespace(headers=_FakeRawHeaders(set_cookies))


def test_authorization_header_is_forwarded(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.get(
        "/api/tasks",
        headers={"Authorization": "Bearer abc.def.ghi"},
    )

    assert response.status_code == 200
    assert captured["headers"]["Authorization"] == "Bearer abc.def.ghi"


def test_single_set_cookie_is_forwarded(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(set_cookies=["session=abc123; Path=/; HttpOnly"]),
    )
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})
    cookies = response.headers.getlist("Set-Cookie")
    assert cookies == ["session=abc123; Path=/; HttpOnly"]


def test_multiple_set_cookie_headers_are_preserved(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(
            set_cookies=[
                "session=abc123; Path=/; HttpOnly",
                "csrf_token=xyz789; Path=/",
            ]
        ),
    )
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})
    cookies = response.headers.getlist("Set-Cookie")
    assert "session=abc123; Path=/; HttpOnly" in cookies
    assert "csrf_token=xyz789; Path=/" in cookies
    assert len(cookies) == 2


def test_relative_location_header_is_forwarded_as_is(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=302, headers={"Location": "/tasks/1"}),
    )
    response = client.get("/tasks/1")
    assert response.status_code == 302
    assert response.headers["Location"] == "/tasks/1"


def test_absolute_location_header_is_rewritten_to_gateway_host(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(
            status_code=302,
            headers={"Location": "http://task-service:5000/tasks/1"},
        ),
    )
    response = client.get("/tasks/1")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost/tasks/1"


def test_query_params_are_forwarded(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.get("/api/tasks?status=pending")

    assert response.status_code == 200
    assert captured["params"]["status"] == "pending"


def test_request_body_is_forwarded(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse(status_code=201)

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.post(
        "/api/tasks",
        json={"title": "Forward me"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert b'"title": "Forward me"' in captured["data"]


@pytest.mark.parametrize("status_code", [404, 500])
def test_downstream_status_code_is_propagated(client, monkeypatch, status_code):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=status_code),
    )
    response = client.get("/api/tasks")
    assert response.status_code == status_code

