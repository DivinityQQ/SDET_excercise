"""
Service Isolation Tests for Auth and Task Microservices.

These tests verify that each microservice can operate independently of
the other.  In a real deployment the auth service might be down for
maintenance while the task service continues to serve requests using
locally-verified JWTs.  Likewise, the auth service should be able to
register and login users without the task service being reachable.

This is a critical microservices security and resilience concern:
tenant data must never leak across user boundaries, and a single
service failure must not cascade into a full system outage.

Key SDET Concepts Demonstrated:
- Service independence testing (each service works in isolation)
- Locally-minted JWT tokens vs. tokens from the auth service
- Health-check endpoint validation for container orchestration
- Verifying that no hidden coupling exists between services
"""

from __future__ import annotations

import pytest

from shared.test_helpers import create_test_token

pytestmark = [pytest.mark.cross_service, pytest.mark.isolation]


def test_task_service_health_without_auth_dependency(task_client):
    """Test that the task service health endpoint works without the auth service."""
    # Arrange -- no setup needed; we only start the task service

    # Act
    response = task_client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.get_json()["service"] == "tasks"


def test_task_api_works_with_local_token_when_auth_service_not_involved(
    task_client,
    task_service_app,
):
    """Test that the task API accepts a locally-minted JWT without calling auth."""
    # Arrange
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

    # Act
    create_response = task_client.post("/api/tasks", json={"title": "Local token task"}, headers=headers)

    # Assert
    assert create_response.status_code == 201

    list_response = task_client.get("/api/tasks", headers=headers)
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1


def test_auth_service_register_and_login_independently(auth_client):
    """Test that the auth service can register and login without the task service."""
    # Arrange
    user_data = {
        "username": "iso_auth_user",
        "email": "iso_auth_user@example.com",
        "password": "StrongPass123!",
    }

    # Act -- register
    register_response = auth_client.post(
        "/api/auth/register",
        json=user_data,
    )

    # Assert -- registration succeeds
    assert register_response.status_code == 201

    # Act -- login
    login_response = auth_client.post(
        "/api/auth/login",
        json={"username": "iso_auth_user", "password": "StrongPass123!"},
    )

    # Assert -- login succeeds and returns a token
    assert login_response.status_code == 200
    assert "token" in login_response.get_json()
