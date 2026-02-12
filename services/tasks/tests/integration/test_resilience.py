"""
Resilience tests for task-service runtime dependencies.

Verifies that the task service degrades gracefully when the upstream auth
service is unreachable or unresponsive. API endpoints that only need a
pre-issued JWT should continue to function, while browser-facing view
routes that proxy to the auth service should return a clear 503 error.

Key SDET Concepts Demonstrated:
- Monkeypatching external HTTP calls (requests.post) to simulate failures
- Testing ConnectionError and Timeout exception paths
- Verifying graceful degradation vs. hard failure
- Resilience markers for selective test execution
"""

from __future__ import annotations

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.resilience]


def test_api_routes_work_even_if_auth_service_url_is_unreachable(
    app,
    client,
    db_session,
    api_headers,
):
    """Test that JSON API endpoints still work when AUTH_SERVICE_URL is unreachable."""
    # Arrange — point AUTH_SERVICE_URL to a non-routable host
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"

    # Act
    create_response = client.post(
        "/api/tasks",
        json={"title": "Resilient API task"},
        headers=api_headers,
    )

    list_response = client.get("/api/tasks", headers=api_headers)

    # Assert
    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1


def test_task_health_endpoint_not_affected_by_auth_service_url(app, client, db_session):
    """Test that the health-check endpoint is unaffected by auth service availability."""
    # Arrange
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"

    # Act
    response = client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.get_json()["service"] == "tasks"


def test_view_login_returns_503_when_auth_service_unreachable(app, client, monkeypatch):
    """Test that the login form POST returns 503 when the auth service is down."""
    # Arrange — monkeypatch requests.post to raise ConnectionError
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"

    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )

    # Act
    response = client.post(
        "/login",
        data={"username": "demo", "password": "secret"},
    )

    # Assert
    assert response.status_code == 503
    assert b"Login service unavailable" in response.data


def test_view_register_times_out_gracefully(app, client, monkeypatch):
    """Test that the register form POST returns 503 on a Timeout from the auth service."""
    # Arrange — monkeypatch requests.post to raise Timeout
    app.config["AUTH_SERVICE_URL"] = "http://slow-auth-service"

    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: (_ for _ in ()).throw(requests.Timeout("slow")),
    )

    # Act
    response = client.post(
        "/register",
        data={
            "username": "new_user",
            "email": "new_user@example.com",
            "password": "secret",
        },
    )

    # Assert
    assert response.status_code == 503
    assert b"Registration service timed out" in response.data
