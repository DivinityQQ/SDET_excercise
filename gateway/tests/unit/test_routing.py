"""Unit tests for gateway route-to-service matching."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


class _FakeRawHeaders:
    def getlist(self, _: str) -> list[str]:
        return []


class _FakeResponse:
    status_code = 200
    content = b"{}"
    headers = {}
    raw = SimpleNamespace(headers=_FakeRawHeaders())


def test_auth_route_proxies_to_auth_service(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.post("/api/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 200
    assert captured["url"] == "http://auth-service.test/api/auth/login"


def test_tasks_route_proxies_to_task_service(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert captured["url"] == "http://task-service.test/api/tasks"


def test_root_route_proxies_to_task_service_views(client, monkeypatch):
    captured = {}

    def _fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("gateway_app.routes.requests.request", _fake_request)
    response = client.get("/")

    assert response.status_code == 200
    assert captured["url"] == "http://task-service.test/"

