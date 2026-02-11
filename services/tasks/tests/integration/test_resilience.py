"""Resilience tests for task service runtime dependencies."""

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
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"

    create_response = client.post(
        "/api/tasks",
        json={"title": "Resilient API task"},
        headers=api_headers,
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/tasks", headers=api_headers)
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1


def test_task_health_endpoint_not_affected_by_auth_service_url(app, client, db_session):
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["service"] == "tasks"


def test_view_login_returns_503_when_auth_service_unreachable(app, client, monkeypatch):
    app.config["AUTH_SERVICE_URL"] = "http://unreachable-auth-service"

    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )
    response = client.post(
        "/login",
        data={"username": "demo", "password": "secret"},
    )

    assert response.status_code == 503
    assert b"Login service unavailable" in response.data


def test_view_register_times_out_gracefully(app, client, monkeypatch):
    app.config["AUTH_SERVICE_URL"] = "http://slow-auth-service"

    monkeypatch.setattr(
        "services.tasks.task_app.routes.views.requests.post",
        lambda *_, **__: (_ for _ in ()).throw(requests.Timeout("slow")),
    )
    response = client.post(
        "/register",
        data={
            "username": "new_user",
            "email": "new_user@example.com",
            "password": "secret",
        },
    )

    assert response.status_code == 503
    assert b"Registration service timed out" in response.data
