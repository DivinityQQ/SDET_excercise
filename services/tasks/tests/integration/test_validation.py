"""Integration tests for task endpoint validation and auth failures."""

from __future__ import annotations

import json

import pytest

from shared.test_helpers import create_test_token

pytestmark = pytest.mark.integration


class TestTitleValidation:
    def test_create_task_with_empty_title_returns_400(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": ""}),
            headers=api_headers,
        )
        assert response.status_code == 400

    def test_create_task_with_whitespace_only_title_returns_400(
        self, client, db_session, api_headers
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "   "}),
            headers=api_headers,
        )
        assert response.status_code == 400

    def test_create_task_with_max_length_title_succeeds(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "a" * 200}),
            headers=api_headers,
        )
        assert response.status_code == 201

    def test_create_task_with_title_exceeding_max_length_returns_400(
        self, client, db_session, api_headers
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "a" * 201}),
            headers=api_headers,
        )
        assert response.status_code == 400


class TestStatusValidation:
    @pytest.mark.parametrize("status", ["PENDING", "Pending", "done", "started", "in-progress", "", 123])
    def test_create_task_with_invalid_status_returns_400(
        self, client, db_session, api_headers, status
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "status": status}),
            headers=api_headers,
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("status", ["pending", "in_progress", "completed"])
    def test_create_task_with_valid_status_succeeds(self, client, db_session, api_headers, status):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "status": status}),
            headers=api_headers,
        )
        assert response.status_code == 201


class TestPriorityValidation:
    @pytest.mark.parametrize("priority", ["HIGH", "urgent", "critical", 1, ""])
    def test_create_task_with_invalid_priority_returns_400(
        self, client, db_session, api_headers, priority
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "priority": priority}),
            headers=api_headers,
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("priority", ["low", "medium", "high"])
    def test_create_task_with_valid_priority_succeeds(
        self, client, db_session, api_headers, priority
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "priority": priority}),
            headers=api_headers,
        )
        assert response.status_code == 201


class TestDueDateValidation:
    def test_create_task_with_valid_iso_date_succeeds(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "due_date": "2025-12-31T23:59:59+00:00"}),
            headers=api_headers,
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "due_date", ["not-a-date", "2024-13-01", "2024-01-32", "01/15/2024", "January 15, 2024"]
    )
    def test_create_task_with_invalid_date_format_returns_400(
        self, client, db_session, api_headers, due_date
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "due_date": due_date}),
            headers=api_headers,
        )
        assert response.status_code == 400

    def test_create_task_with_null_due_date_succeeds(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Test Task", "due_date": None}),
            headers=api_headers,
        )
        assert response.status_code == 201


class TestRequestBodyValidation:
    def test_create_task_without_content_type_returns_415(self, client, db_session, api_headers):
        headers = {"Authorization": api_headers["Authorization"]}
        response = client.post("/api/tasks", data='{"title":"Task"}', headers=headers)
        assert response.status_code == 415

    def test_create_task_with_invalid_json_returns_400(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data='{"title": "Invalid JSON",}',
            headers=api_headers,
        )
        assert response.status_code == 400

    def test_update_task_without_content_type_returns_415(self, client, db_session, sample_task, api_headers):
        headers = {"Authorization": api_headers["Authorization"]}
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data='{"title":"Updated"}',
            headers=headers,
        )
        assert response.status_code == 415


class TestEstimatedMinutesValidation:
    def test_create_task_with_valid_estimated_minutes_succeeds(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Estimated Task", "estimated_minutes": 30}),
            headers=api_headers,
        )
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] == 30

    def test_create_task_with_null_estimated_minutes_succeeds(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "No Estimate Task", "estimated_minutes": None}),
            headers=api_headers,
        )
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] is None

    @pytest.mark.parametrize("estimated_minutes", [0, -1, -100, "thirty", 3.5])
    def test_create_task_with_invalid_estimated_minutes_returns_400(
        self, client, db_session, api_headers, estimated_minutes
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Invalid Estimate Task", "estimated_minutes": estimated_minutes}),
            headers=api_headers,
        )
        assert response.status_code == 400

    def test_create_task_with_minimum_valid_estimated_minutes(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Minimum Estimate Task", "estimated_minutes": 1}),
            headers=api_headers,
        )
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] == 1

    def test_update_task_estimated_minutes(self, client, db_session, sample_task, api_headers):
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps({"estimated_minutes": 45}),
            headers=api_headers,
        )
        assert response.status_code == 200
        assert response.get_json()["estimated_minutes"] == 45


class TestAuthValidation:
    def test_missing_authorization_header_returns_401(self, client, db_session):
        response = client.get("/api/tasks")
        assert response.status_code == 401
        assert response.get_json() == {"error": "Missing or invalid Authorization header"}

    def test_malformed_authorization_header_returns_401(self, client, db_session):
        response = client.get("/api/tasks", headers={"Authorization": "Token abc"})
        assert response.status_code == 401
        assert response.get_json() == {"error": "Missing or invalid Authorization header"}

    def test_expired_token_returns_401(self, client, db_session, app):
        token = create_test_token(
            user_id=1,
            username="expired",
            secret=app.config["JWT_SECRET_KEY"],
            expired=True,
        )
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid or expired token"}

    def test_wrong_secret_token_returns_401(self, client, db_session):
        token = create_test_token(
            user_id=1,
            username="wrong_secret",
            secret="different-secret-key-for-tests-987654",
        )
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid or expired token"}

