"""
Integration tests for task endpoint input validation and auth error responses.

Exercises every field-level validation rule (title length, status/priority
enums, due-date format, estimated_minutes bounds), content-type enforcement,
and authentication failure paths against the running Flask application.

Key SDET Concepts Demonstrated:
- Boundary-value analysis (max-length title, minimum estimated_minutes)
- Equivalence partitioning via @pytest.mark.parametrize
- Negative testing for invalid enums, bad JSON, wrong content-type
- Auth-failure scenarios (missing header, malformed header, expired/wrong-key tokens)
"""

from __future__ import annotations

import json

import pytest

from shared.test_helpers import (
    TEST_PRIVATE_KEY,
    create_test_token,
    generate_throwaway_key_pair,
)

pytestmark = pytest.mark.integration


class TestTitleValidation:
    """Tests for task title field validation rules."""

    def test_create_task_with_empty_title_returns_400(self, client, db_session, api_headers):
        """Test that an empty string title is rejected."""
        # Arrange
        payload = {"title": ""}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    def test_create_task_with_whitespace_only_title_returns_400(
        self, client, db_session, api_headers
    ):
        """Test that a whitespace-only title is rejected."""
        # Arrange
        payload = {"title": "   "}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    def test_create_task_with_max_length_title_succeeds(self, client, db_session, api_headers):
        """Test that a title at exactly the 200-character limit is accepted."""
        # Arrange
        payload = {"title": "a" * 200}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201

    def test_create_task_with_title_exceeding_max_length_returns_400(
        self, client, db_session, api_headers
    ):
        """Test that a title exceeding 200 characters is rejected."""
        # Arrange
        payload = {"title": "a" * 201}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400


class TestStatusValidation:
    """Tests for task status enum validation."""

    @pytest.mark.parametrize("status", ["PENDING", "Pending", "done", "started", "in-progress", "", 123])
    def test_create_task_with_invalid_status_returns_400(
        self, client, db_session, api_headers, status
    ):
        """Test that non-canonical status values are rejected (case-sensitive enum)."""
        # Arrange — parametrized 'status' covers wrong case, unknown values, empty, numeric
        payload = {"title": "Test Task", "status": status}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.parametrize("status", ["pending", "in_progress", "completed"])
    def test_create_task_with_valid_status_succeeds(self, client, db_session, api_headers, status):
        """Test that each canonical status value is accepted."""
        # Arrange — parametrized 'status' is one of the valid TaskStatus values
        payload = {"title": "Test Task", "status": status}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201


class TestPriorityValidation:
    """Tests for task priority enum validation."""

    @pytest.mark.parametrize("priority", ["HIGH", "urgent", "critical", 1, ""])
    def test_create_task_with_invalid_priority_returns_400(
        self, client, db_session, api_headers, priority
    ):
        """Test that non-canonical priority values are rejected."""
        # Arrange — parametrized 'priority' covers wrong case, unknown values, numeric, empty
        payload = {"title": "Test Task", "priority": priority}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.parametrize("priority", ["low", "medium", "high"])
    def test_create_task_with_valid_priority_succeeds(
        self, client, db_session, api_headers, priority
    ):
        """Test that each canonical priority value is accepted."""
        # Arrange — parametrized 'priority' is one of the valid TaskPriority values
        payload = {"title": "Test Task", "priority": priority}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201


class TestDueDateValidation:
    """Tests for task due_date field validation (ISO 8601 format)."""

    def test_create_task_with_valid_iso_date_succeeds(self, client, db_session, api_headers):
        """Test that a well-formed ISO 8601 datetime string is accepted."""
        # Arrange
        payload = {"title": "Test Task", "due_date": "2025-12-31T23:59:59+00:00"}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "due_date", ["not-a-date", "2024-13-01", "2024-01-32", "01/15/2024", "January 15, 2024"]
    )
    def test_create_task_with_invalid_date_format_returns_400(
        self, client, db_session, api_headers, due_date
    ):
        """Test that non-ISO-8601 date strings are rejected."""
        # Arrange — parametrized 'due_date' covers plain text, out-of-range, US format, long-form
        payload = {"title": "Test Task", "due_date": due_date}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    def test_create_task_with_null_due_date_succeeds(self, client, db_session, api_headers):
        """Test that explicitly passing null for due_date is accepted (optional field)."""
        # Arrange
        payload = {"title": "Test Task", "due_date": None}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201


class TestRequestBodyValidation:
    """Tests for content-type and JSON-body parsing rules."""

    def test_create_task_without_content_type_returns_415(self, client, db_session, api_headers):
        """Test that omitting Content-Type header returns 415 Unsupported Media Type."""
        # Arrange — strip Content-Type, keep only Authorization
        headers = {"Authorization": api_headers["Authorization"]}

        # Act
        response = client.post("/api/tasks", data='{"title":"Task"}', headers=headers)

        # Assert
        assert response.status_code == 415

    def test_create_task_with_invalid_json_returns_400(self, client, db_session, api_headers):
        """Test that malformed JSON in the request body returns 400."""
        # Arrange
        invalid_json = '{"title": "Invalid JSON",}'

        # Act
        response = client.post(
            "/api/tasks",
            data=invalid_json,
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    def test_update_task_without_content_type_returns_415(self, client, db_session, sample_task, api_headers):
        """Test that a PUT without Content-Type returns 415."""
        # Arrange — strip Content-Type, keep only Authorization
        headers = {"Authorization": api_headers["Authorization"]}

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data='{"title":"Updated"}',
            headers=headers,
        )

        # Assert
        assert response.status_code == 415


class TestEstimatedMinutesValidation:
    """Tests for the optional estimated_minutes integer field."""

    def test_create_task_with_valid_estimated_minutes_succeeds(self, client, db_session, api_headers):
        """Test that a positive integer for estimated_minutes is accepted."""
        # Arrange
        payload = {"title": "Estimated Task", "estimated_minutes": 30}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] == 30

    def test_create_task_with_null_estimated_minutes_succeeds(self, client, db_session, api_headers):
        """Test that explicitly passing null for estimated_minutes is accepted."""
        # Arrange
        payload = {"title": "No Estimate Task", "estimated_minutes": None}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] is None

    @pytest.mark.parametrize("estimated_minutes", [0, -1, -100, "thirty", 3.5])
    def test_create_task_with_invalid_estimated_minutes_returns_400(
        self, client, db_session, api_headers, estimated_minutes
    ):
        """Test that zero, negative, non-integer, and string values are rejected."""
        # Arrange — parametrized 'estimated_minutes' covers zero, negative, string, float
        payload = {"title": "Invalid Estimate Task", "estimated_minutes": estimated_minutes}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400

    def test_create_task_with_minimum_valid_estimated_minutes(self, client, db_session, api_headers):
        """Test that the minimum valid value (1) is accepted."""
        # Arrange
        payload = {"title": "Minimum Estimate Task", "estimated_minutes": 1}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        assert response.get_json()["estimated_minutes"] == 1

    def test_update_task_estimated_minutes(self, client, db_session, sample_task, api_headers):
        """Test that estimated_minutes can be updated on an existing task via PUT."""
        # Arrange - provided by sample_task fixture

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps({"estimated_minutes": 45}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 200
        assert response.get_json()["estimated_minutes"] == 45


class TestAuthValidation:
    """Tests for authentication error responses on task endpoints."""

    def test_missing_authorization_header_returns_401(self, client, db_session):
        """Test that requests with no Authorization header receive 401."""
        # Arrange - no auth headers provided

        # Act
        response = client.get("/api/tasks")

        # Assert
        assert response.status_code == 401
        assert response.get_json() == {"error": "Missing or invalid Authorization header"}

    def test_malformed_authorization_header_returns_401(self, client, db_session):
        """Test that a non-Bearer auth scheme is rejected with 401."""
        # Arrange
        headers = {"Authorization": "Token abc"}

        # Act
        response = client.get("/api/tasks", headers=headers)

        # Assert
        assert response.status_code == 401
        assert response.get_json() == {"error": "Missing or invalid Authorization header"}

    def test_expired_token_returns_401(self, client, db_session, app):
        """Test that an expired JWT token returns 401."""
        # Arrange
        token = create_test_token(
            user_id=1,
            username="expired",
            private_key=TEST_PRIVATE_KEY,
            expired=True,
        )

        # Act
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid or expired token"}

    def test_wrong_key_token_returns_401(self, client, db_session):
        """Test that a token signed with a different private key is rejected with 401."""
        # Arrange
        wrong_private_key, _ = generate_throwaway_key_pair()
        token = create_test_token(
            user_id=1,
            username="wrong_key",
            private_key=wrong_private_key,
        )

        # Act
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid or expired token"}
