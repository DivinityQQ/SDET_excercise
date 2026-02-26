"""
Cross-Service Auth-to-Task End-to-End Flow Tests.

These tests exercise the full user journey that spans both microservices:
register on auth, login to get a JWT, then use that JWT to perform CRUD
operations on the task service.  Unlike unit tests that mock the "other"
service, these tests spin up both real Flask apps and pass real tokens
between them, catching integration mismatches early.

Key SDET Concepts Demonstrated:
- End-to-end flow testing across independently deployed services
- Helper functions that encapsulate multi-step API sequences
- Positive path: register -> login -> create -> list -> get
- Negative path: cross-user access denied (tenant isolation)
- Reusable request header builders for authenticated calls
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.cross_service


def _register_user(auth_client, username: str, email: str, password: str) -> None:
    """Register a new user via the auth service and assert success."""
    response = auth_client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 201


def _login_user(auth_client, username: str, password: str) -> str:
    """Log in via the auth service and return the JWT token string."""
    response = auth_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def _task_headers(token: str) -> dict[str, str]:
    """Build standard request headers for authenticated task API calls."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def test_register_login_and_task_crud_flow(auth_client, task_client):
    """Test that a user can register, login, and perform full task CRUD."""
    # Arrange
    _register_user(auth_client, "flow_user", "flow_user@example.com", "StrongPass123!")
    token = _login_user(auth_client, "flow_user", "StrongPass123!")
    headers = _task_headers(token)

    # Act -- create a task
    create_response = task_client.post(
        "/api/tasks",
        json={"title": "Cross-service Task"},
        headers=headers,
    )

    # Assert -- task is created and retrievable
    assert create_response.status_code == 201
    task_id = create_response.get_json()["id"]

    list_response = task_client.get("/api/tasks", headers=headers)
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1

    get_response = task_client.get(f"/api/tasks/{task_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.get_json()["title"] == "Cross-service Task"


@pytest.mark.security
def test_user_a_cannot_access_user_b_tasks(auth_client, task_client):
    """Test that one user's tasks are invisible to another user."""
    # Arrange
    _register_user(auth_client, "user_a", "user_a@example.com", "StrongPass123!")
    _register_user(auth_client, "user_b", "user_b@example.com", "StrongPass123!")

    token_a = _login_user(auth_client, "user_a", "StrongPass123!")
    token_b = _login_user(auth_client, "user_b", "StrongPass123!")
    headers_a = _task_headers(token_a)
    headers_b = _task_headers(token_b)

    # Act -- user A creates a task
    create_response = task_client.post(
        "/api/tasks",
        json={"title": "A private task"},
        headers=headers_a,
    )
    assert create_response.status_code == 201
    task_id = create_response.get_json()["id"]

    # Assert -- user B cannot see user A's task
    get_as_b = task_client.get(f"/api/tasks/{task_id}", headers=headers_b)
    assert get_as_b.status_code == 404

    list_as_b = task_client.get("/api/tasks", headers=headers_b)
    assert list_as_b.status_code == 200
    assert list_as_b.get_json()["count"] == 0
