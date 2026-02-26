"""Security tests for adversarial input handling on task endpoints."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


SQLI_PAYLOAD = "x'); DROP TABLE tasks;--"


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def test_sqli_like_strings_are_stored_as_plain_text(task_client, token_for_user):
    """Injected SQL-like content should be persisted literally, not executed."""
    token, _ = token_for_user()

    create_response = task_client.post(
        "/api/tasks",
        json={"title": SQLI_PAYLOAD, "description": SQLI_PAYLOAD},
        headers=_auth_headers(token),
    )

    assert create_response.status_code == 201
    body = create_response.get_json()
    assert body["title"] == SQLI_PAYLOAD
    assert body["description"] == SQLI_PAYLOAD


def test_sqli_like_filter_does_not_bypass_query_constraints(task_client, token_for_user):
    """SQL-like filter input must not return unintended rows."""
    token_a, _ = token_for_user()
    token_b, _ = token_for_user()

    create_a = task_client.post(
        "/api/tasks",
        json={"title": "User A task", "status": "pending"},
        headers=_auth_headers(token_a),
    )
    assert create_a.status_code == 201

    filter_response = task_client.get(
        "/api/tasks",
        query_string={"status": "pending' OR '1'='1"},
        headers=_auth_headers(token_b),
    )

    assert filter_response.status_code == 200
    payload = filter_response.get_json()
    assert payload["count"] == 0
    assert payload["tasks"] == []


def test_malicious_sort_parameter_does_not_break_task_queries(task_client, token_for_user):
    """Unsupported sort expressions should be ignored without side effects."""
    token, _ = token_for_user()
    headers = _auth_headers(token)

    first_create = task_client.post(
        "/api/tasks",
        json={"title": "Task before malicious sort"},
        headers=headers,
    )
    assert first_create.status_code == 201

    list_response = task_client.get(
        "/api/tasks",
        query_string={"sort": "created_at; DROP TABLE tasks", "order": "desc"},
        headers=headers,
    )
    assert list_response.status_code == 200

    second_create = task_client.post(
        "/api/tasks",
        json={"title": "Task after malicious sort"},
        headers=headers,
    )
    assert second_create.status_code == 201

    final_list = task_client.get("/api/tasks", headers=headers)
    assert final_list.status_code == 200
    assert final_list.get_json()["count"] == 2
