"""
Resilience tests for the API-only task service.

After frontend extraction, task-service has no runtime dependency on auth-service
for request handling. These tests keep lightweight checks that core API endpoints
remain functional in isolation.
"""

from __future__ import annotations

import pytest
pytestmark = [pytest.mark.integration, pytest.mark.resilience]


def test_api_routes_work_without_external_auth_calls(
    client,
    db_session,
    api_headers,
):
    """API routes work with a valid token and no auth-service calls."""

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


def test_task_health_endpoint_is_independent(client, db_session):
    """Health endpoint works without any external service dependency."""

    # Act
    response = client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.get_json()["service"] == "tasks"
