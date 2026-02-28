"""
Security tests for adversarial input handling on task endpoints.

Submits classic SQL-injection payloads through task fields, query-string
filters, and sort parameters to verify the API treats them as opaque
data rather than executable SQL.  The ORM's parameterised queries should
neutralise these payloads, but these tests confirm the behaviour at the
HTTP boundary (OWASP A03 – Injection).

Key SDET Concepts Demonstrated:
- Injection payload construction (DROP TABLE, tautology-based OR)
- Multi-user isolation verification under adversarial input
- Before-and-after state checks to detect silent data corruption
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


SQLI_PAYLOAD = "x'); DROP TABLE tasks;--"


def _auth_headers(token: str) -> dict[str, str]:
    """Build request headers with a Bearer token for authenticated API calls."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def test_sqli_like_strings_are_stored_as_plain_text(task_client, token_for_user):
    """Injected SQL-like content should be persisted literally, not executed."""
    # Arrange
    token, _ = token_for_user()

    # Act — store a SQL-injection payload in both title and description
    create_response = task_client.post(
        "/api/tasks",
        json={"title": SQLI_PAYLOAD, "description": SQLI_PAYLOAD},
        headers=_auth_headers(token),
    )

    # Assert — payload is echoed back verbatim, not interpreted
    assert create_response.status_code == 201
    body = create_response.get_json()
    assert body["title"] == SQLI_PAYLOAD
    assert body["description"] == SQLI_PAYLOAD


def test_sqli_like_filter_does_not_bypass_query_constraints(task_client, token_for_user):
    """SQL-like filter input must not return unintended rows."""
    # Arrange — two users; only user A creates a task
    token_a, _ = token_for_user()
    token_b, _ = token_for_user()

    create_a = task_client.post(
        "/api/tasks",
        json={"title": "User A task", "status": "pending"},
        headers=_auth_headers(token_a),
    )
    assert create_a.status_code == 201

    # Act — user B sends a tautology-based injection via the status filter
    filter_response = task_client.get(
        "/api/tasks",
        query_string={"status": "pending' OR '1'='1"},
        headers=_auth_headers(token_b),
    )

    # Assert — injection has no effect; user B still sees zero tasks
    assert filter_response.status_code == 200
    payload = filter_response.get_json()
    assert payload["count"] == 0
    assert payload["tasks"] == []


def test_malicious_sort_parameter_does_not_break_task_queries(task_client, token_for_user):
    """Unsupported sort expressions should be ignored without side effects."""
    # Arrange — create a task so the table is non-empty
    token, _ = token_for_user()
    headers = _auth_headers(token)

    first_create = task_client.post(
        "/api/tasks",
        json={"title": "Task before malicious sort"},
        headers=headers,
    )
    assert first_create.status_code == 201

    # Act — inject a DROP TABLE statement via the sort parameter
    list_response = task_client.get(
        "/api/tasks",
        query_string={"sort": "created_at; DROP TABLE tasks", "order": "desc"},
        headers=headers,
    )
    assert list_response.status_code == 200

    # Assert — table survives; a second insert and final count prove no corruption
    second_create = task_client.post(
        "/api/tasks",
        json={"title": "Task after malicious sort"},
        headers=headers,
    )
    assert second_create.status_code == 201

    final_list = task_client.get("/api/tasks", headers=headers)
    assert final_list.status_code == 200
    assert final_list.get_json()["count"] == 2
