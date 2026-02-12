"""
Resilience tests for gateway proxy failures.

Verifies that the gateway degrades gracefully when downstream services
are unavailable or misbehaving.  The three core failure modes covered
are:

1. **Timeout** -- the downstream service takes too long to respond.
2. **Connection error** -- the downstream service is completely unreachable.
3. **Server error** -- the downstream service returns a 500 Internal
   Server Error, which the gateway must propagate faithfully.

Each test monkeypatches ``requests.request`` to raise the appropriate
exception (or return a 500 response), then asserts that the gateway
returns a well-formed 502 or propagated status to the caller.

Key SDET Concepts Demonstrated:
- Negative / failure-path testing for service resilience
- Simulating network-level errors with monkeypatched exceptions
- Verifying structured JSON error payloads under failure conditions
- Ensuring the gateway never exposes raw stack traces to callers
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

pytestmark = pytest.mark.integration


class _FakeRawHeaders:
    """Minimal stand-in for ``urllib3.HTTPResponse.headers`` used by the proxy."""

    def getlist(self, _: str) -> list[str]:
        return []


class _FakeResponse:
    """Configurable stand-in for ``requests.Response`` that models a downstream error."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.content = b'{"error":"downstream"}'
        self.headers = {"Content-Type": "application/json"}
        self.raw = SimpleNamespace(headers=_FakeRawHeaders())


def test_auth_service_timeout_returns_502(client, monkeypatch):
    """Test that a downstream timeout is surfaced as a 502 with a clear message."""
    # Arrange
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )

    # Act
    response = client.get("/api/auth/verify")

    # Assert
    assert response.status_code == 502
    assert response.get_json() == {"error": "Downstream request timed out"}


def test_task_service_unreachable_returns_502(client, monkeypatch):
    """Test that an unreachable service is surfaced as a 502 with a clear message."""
    # Arrange
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: (_ for _ in ()).throw(requests.ConnectionError("unreachable")),
    )

    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 502
    assert response.get_json() == {"error": "Downstream service unavailable"}


def test_downstream_500_is_propagated(client, monkeypatch):
    """Test that a 500 from the downstream service is forwarded to the caller."""
    # Arrange
    monkeypatch.setattr(
        "gateway_app.routes.requests.request",
        lambda **_: _FakeResponse(status_code=500),
    )

    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 500
