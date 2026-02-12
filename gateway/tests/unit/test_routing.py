"""
Unit tests for gateway route-to-service matching.

Verifies that the gateway correctly maps incoming URL paths to the
appropriate downstream microservice.  Each test monkeypatches the
outbound ``requests.request`` call so that no real HTTP traffic is
generated; instead, a lightweight fake response is returned and the
captured request kwargs are inspected to confirm the target URL.

Key SDET Concepts Demonstrated:
- Monkeypatching to replace I/O-bound dependencies with fakes
- URL-based route matching assertions (prefix routing)
- Lightweight stub objects that satisfy the interface contract
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


class _FakeRawHeaders:
    """Minimal stand-in for ``urllib3.HTTPResponse.headers`` used by the proxy."""

    def getlist(self, _: str) -> list[str]:
        return []


class _FakeResponse:
    """Minimal stand-in for ``requests.Response`` returned by the proxy layer."""

    status_code = 200
    content = b"{}"
    headers = {}
    raw = SimpleNamespace(headers=_FakeRawHeaders())


def test_auth_route_proxies_to_auth_service(client, monkeypatch):
    """Test that /api/auth/* requests are forwarded to the auth service."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})

    # Assert
    assert response.status_code == 200
    assert captured["url"] == "http://auth-service.test/api/auth/login"


def test_tasks_route_proxies_to_task_service(client, monkeypatch):
    """Test that /api/tasks requests are forwarded to the task service."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 200
    assert captured["url"] == "http://task-service.test/api/tasks"


def test_root_route_proxies_to_task_service_views(client, monkeypatch):
    """Test that the root path (/) is forwarded to the task service for view rendering."""
    # Arrange
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)

    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 200
    assert captured["url"] == "http://task-service.test/"
