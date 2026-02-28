"""
Security tests for mass-assignment hardening on task endpoints.

Sends requests that include extra fields (id, user_id, created_at,
updated_at, is_admin) alongside legitimate task data and verifies the
API silently drops them rather than binding them to the model.  Covers
both the creation and update paths (OWASP A04 – Insecure Design).

Key SDET Concepts Demonstrated:
- Adversarial payload construction with protected / non-existent fields
- Positive-negative hybrid assertions (201 success but fields ignored)
- Ownership-invariant verification on update path
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def _auth_headers(token: str) -> dict[str, str]:
    """Build request headers with a Bearer token for authenticated API calls."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def test_create_task_ignores_protected_fields(task_client, token_for_user):
    """Task creation must ignore user-controlled identity/system fields."""
    # Arrange — payload includes protected fields the API must drop
    token, user = token_for_user()
    payload = {
        "id": 999999,
        "user_id": 424242,
        "title": "Mass assignment probe",
        "description": "Attempt to override protected fields",
        "created_at": "1990-01-01T00:00:00+00:00",
        "updated_at": "1990-01-01T00:00:00+00:00",
        "is_admin": True,
    }

    # Act
    response = task_client.post("/api/tasks", json=payload, headers=_auth_headers(token))

    # Assert — task is created but every protected field is server-assigned
    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] != payload["id"]
    assert body["user_id"] == user["id"]
    assert body["user_id"] != payload["user_id"]
    assert body["created_at"] != payload["created_at"]
    assert body["updated_at"] != payload["updated_at"]
    assert "is_admin" not in body


def test_update_task_cannot_reassign_user_id(task_client, token_for_user):
    """Task updates must not allow ownership reassignment."""
    # Arrange — create a task owned by the authenticated user
    token, user = token_for_user()
    headers = _auth_headers(token)

    create_response = task_client.post(
        "/api/tasks",
        json={"title": "Owned task", "description": "Original owner"},
        headers=headers,
    )
    assert create_response.status_code == 201
    task_id = create_response.get_json()["id"]

    # Act — attempt to reassign ownership via user_id in update payload
    update_response = task_client.put(
        f"/api/tasks/{task_id}",
        json={"title": "Updated title", "user_id": user["id"] + 9999},
        headers=headers,
    )

    # Assert — title updates normally but user_id remains unchanged
    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated["title"] == "Updated title"
    assert updated["user_id"] == user["id"]
