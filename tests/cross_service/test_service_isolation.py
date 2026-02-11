"""Service isolation tests for auth and task services."""

from __future__ import annotations

import pytest

from shared.test_helpers import create_test_token

pytestmark = [pytest.mark.cross_service, pytest.mark.isolation]


def test_task_service_health_without_auth_dependency(task_client):
    response = task_client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["service"] == "tasks"


def test_task_api_works_with_local_token_when_auth_service_not_involved(
    task_client,
    task_service_app,
):
    token = create_test_token(
        user_id=1,
        username="local_user",
        secret=task_service_app.config["JWT_SECRET_KEY"],
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    create_response = task_client.post("/api/tasks", json={"title": "Local token task"}, headers=headers)
    assert create_response.status_code == 201

    list_response = task_client.get("/api/tasks", headers=headers)
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1


def test_auth_service_register_and_login_independently(auth_client):
    register_response = auth_client.post(
        "/api/auth/register",
        json={
            "username": "iso_auth_user",
            "email": "iso_auth_user@example.com",
            "password": "StrongPass123!",
        },
    )
    assert register_response.status_code == 201

    login_response = auth_client.post(
        "/api/auth/login",
        json={"username": "iso_auth_user", "password": "StrongPass123!"},
    )
    assert login_response.status_code == 200
    assert "token" in login_response.get_json()

