"""Resilience tests for gateway proxy failures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

pytestmark = pytest.mark.integration


class _FakeRawHeaders:
    def getlist(self, _: str) -> list[str]:
        return []


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.content = b'{"error":"downstream"}'
        self.headers = {"Content-Type": "application/json"}
        self.raw = SimpleNamespace(headers=_FakeRawHeaders())


def test_auth_service_timeout_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )
    response = client.get("/api/auth/verify")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Downstream request timed out"}


def test_task_service_unreachable_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: (_ for _ in ()).throw(requests.ConnectionError("unreachable")),
    )
    response = client.get("/api/tasks")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Downstream service unavailable"}


def test_downstream_500_is_propagated(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=500),
    )
    response = client.get("/api/tasks")

    assert response.status_code == 500

