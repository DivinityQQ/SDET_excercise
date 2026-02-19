"""
Integration tests for gateway proxy behavior.

Exercises the full request/response pipeline through the gateway to
verify that headers, cookies, query parameters, request bodies, status
codes, and redirect Location headers are faithfully forwarded (or
correctly rewritten) between the client and the downstream service.

Each test monkeypatches ``requests.request`` with a configurable fake
so that no real network calls are made, while still exercising the
gateway's proxy plumbing end-to-end inside the Flask test client.

Key SDET Concepts Demonstrated:
- Header forwarding verification (Authorization, Set-Cookie)
- Multi-value header preservation (multiple Set-Cookie entries)
- Redirect rewriting (absolute URLs mapped back to the gateway host)
- Query-string and request-body pass-through assertions
- Parametrized tests for downstream status-code propagation
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration


class _FakeRawHeaders:
    """Simulate ``urllib3`` raw headers with optional Set-Cookie support."""

    def __init__(self, set_cookies: list[str] | None = None):
        self._set_cookies = set_cookies or []

    def getlist(self, name: str) -> list[str]:
        if name.lower() == "set-cookie":
            return self._set_cookies
        return []


class _FakeResponse:
    """Configurable stand-in for ``requests.Response`` used by the proxy layer."""

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
    """Test that the Authorization header is passed through to the downstream service."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway.gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.get(
        "/api/tasks",
        headers={"Authorization": "Bearer abc.def.ghi"},
    )

    # Assert
    assert response.status_code == 200
    assert captured["headers"]["Authorization"] == "Bearer abc.def.ghi"


def test_single_set_cookie_is_forwarded(client, monkeypatch):
    """Test that a single Set-Cookie header from downstream reaches the client."""
    # Arrange
    monkeypatch.setattr(
        "gateway.gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(set_cookies=["session=abc123; Path=/; HttpOnly"]),
    )

    # Act
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})

    # Assert
    cookies = response.headers.getlist("Set-Cookie")
    assert cookies == ["session=abc123; Path=/; HttpOnly"]


def test_multiple_set_cookie_headers_are_preserved(client, monkeypatch):
    """Test that multiple Set-Cookie headers are all forwarded without merging."""
    # Arrange
    monkeypatch.setattr(
        "gateway.gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(
            set_cookies=[
                "session=abc123; Path=/; HttpOnly",
                "csrf_token=xyz789; Path=/",
            ]
        ),
    )

    # Act
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})

    # Assert
    cookies = response.headers.getlist("Set-Cookie")
    assert "session=abc123; Path=/; HttpOnly" in cookies
    assert "csrf_token=xyz789; Path=/" in cookies
    assert len(cookies) == 2


def test_relative_location_header_is_forwarded_as_is(client, monkeypatch):
    """Test that a relative Location header is passed through unchanged."""
    # Arrange
    monkeypatch.setattr(
        "gateway.gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=302, headers={"Location": "/tasks/1"}),
    )

    # Act
    response = client.get("/tasks/1")

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"] == "/tasks/1"


def test_absolute_location_header_is_rewritten_to_gateway_host(client, monkeypatch):
    """Test that an absolute Location URL is rewritten to use the gateway's host."""
    # Arrange
    monkeypatch.setattr(
        "gateway.gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(
            status_code=302,
            headers={"Location": "http://task-service:5000/tasks/1"},
        ),
    )

    # Act
    response = client.get("/tasks/1")

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost/tasks/1"


def test_query_params_are_forwarded(client, monkeypatch):
    """Test that query-string parameters are passed through to the downstream URL."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway.gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.get("/api/tasks?status=pending")

    # Assert
    assert response.status_code == 200
    assert captured["params"]["status"] == "pending"


def test_request_body_is_forwarded(client, monkeypatch):
    """Test that the JSON request body is forwarded to the downstream service."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse(status_code=201)

    monkeypatch.setattr("gateway.gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.post(
        "/api/tasks",
        json={"title": "Forward me"},
        headers={"Authorization": "Bearer token"},
    )

    # Assert
    assert response.status_code == 201
    assert b'"title": "Forward me"' in captured["data"]


@pytest.mark.parametrize("status_code", [404, 500])
def test_downstream_status_code_is_propagated(client, monkeypatch, status_code):
    """Test that non-200 status codes from the downstream service are returned as-is."""
    # Arrange
    monkeypatch.setattr(
        "gateway.gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=status_code),
    )

    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == status_code
