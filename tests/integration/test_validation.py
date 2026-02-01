"""
API Validation Tests for Task endpoints.

This module tests input validation, boundary conditions, and error
handling for the API endpoints. These tests ensure the API properly
validates and rejects invalid input.

Key SDET Concepts Demonstrated:
- Boundary value testing
- Negative testing (testing invalid inputs)
- Parameterized testing for multiple invalid cases
- Error message validation
"""

import pytest
import json
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.integration


class TestTitleValidation:
    """Tests for task title field validation."""

    @pytest.mark.api
    def test_create_task_with_empty_title_returns_400(
        self, client, db_session, api_headers
    ):
        """
        Test that empty title is rejected.

        Boundary: Empty string is below minimum length.
        """
        # Arrange
        data = {"title": ""}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        error_data = json.loads(response.data)
        assert "error" in error_data
        assert "title" in error_data["error"].lower()

    @pytest.mark.api
    def test_create_task_with_whitespace_only_title_returns_400(
        self, client, db_session, api_headers
    ):
        """
        Test that whitespace-only title is rejected.

        Edge case: Title with only spaces should be treated as empty.
        """
        # Arrange
        data = {"title": "   "}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.api
    def test_create_task_with_max_length_title_succeeds(
        self, client, db_session, api_headers
    ):
        """
        Test that title at maximum length (200 chars) is accepted.

        Boundary: Exactly at the maximum allowed length.
        """
        # Arrange
        max_length_title = "a" * 200
        data = {"title": max_length_title}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["title"] == max_length_title

    @pytest.mark.api
    def test_create_task_with_title_exceeding_max_length_returns_400(
        self, client, db_session, api_headers
    ):
        """
        Test that title exceeding maximum length (201 chars) is rejected.

        Boundary: One character over the maximum allowed length.
        """
        # Arrange
        too_long_title = "a" * 201
        data = {"title": too_long_title}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        error_data = json.loads(response.data)
        assert "error" in error_data


class TestStatusValidation:
    """Tests for task status field validation."""

    @pytest.mark.api
    @pytest.mark.parametrize("invalid_status", [
        "PENDING",          # Wrong case
        "Pending",          # Title case
        "done",             # Invalid value
        "started",          # Invalid value
        "in-progress",      # Wrong format (hyphen vs underscore)
        "",                 # Empty string
        123,                # Wrong type
    ])
    def test_create_task_with_invalid_status_returns_400(
        self, client, db_session, api_headers, invalid_status
    ):
        """
        Test that invalid status values are rejected.

        This demonstrates parameterized testing for multiple
        invalid input variations.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "status": invalid_status
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        error_data = json.loads(response.data)
        assert "error" in error_data

    @pytest.mark.api
    @pytest.mark.parametrize("valid_status", [
        "pending",
        "in_progress",
        "completed"
    ])
    def test_create_task_with_valid_status_succeeds(
        self, client, db_session, api_headers, valid_status
    ):
        """
        Test that all valid status values are accepted.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "status": valid_status
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["status"] == valid_status


class TestPriorityValidation:
    """Tests for task priority field validation."""

    @pytest.mark.api
    @pytest.mark.parametrize("invalid_priority", [
        "HIGH",             # Wrong case
        "urgent",           # Invalid value
        "critical",         # Invalid value
        "1",                # Numeric string
        "",                 # Empty string
    ])
    def test_create_task_with_invalid_priority_returns_400(
        self, client, db_session, api_headers, invalid_priority
    ):
        """
        Test that invalid priority values are rejected.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "priority": invalid_priority
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.api
    @pytest.mark.parametrize("valid_priority", ["low", "medium", "high"])
    def test_create_task_with_valid_priority_succeeds(
        self, client, db_session, api_headers, valid_priority
    ):
        """
        Test that all valid priority values are accepted.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "priority": valid_priority
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["priority"] == valid_priority


class TestDueDateValidation:
    """Tests for task due_date field validation."""

    @pytest.mark.api
    def test_create_task_with_valid_iso_date_succeeds(
        self, client, db_session, api_headers
    ):
        """
        Test that valid ISO format date is accepted.
        """
        # Arrange
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        data = {
            "title": "Test Task",
            "due_date": future_date
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["due_date"] is not None

    @pytest.mark.api
    @pytest.mark.parametrize("invalid_date", [
        "not-a-date",
        "2024-13-01",       # Invalid month
        "2024-01-32",       # Invalid day
        "01/15/2024",       # Wrong format
        "January 15, 2024", # Wrong format
    ])
    def test_create_task_with_invalid_date_format_returns_400(
        self, client, db_session, api_headers, invalid_date
    ):
        """
        Test that invalid date formats are rejected.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "due_date": invalid_date
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.api
    def test_create_task_with_null_due_date_succeeds(
        self, client, db_session, api_headers
    ):
        """
        Test that null due_date is accepted (optional field).
        """
        # Arrange
        data = {
            "title": "Test Task",
            "due_date": None
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["due_date"] is None


class TestRequestBodyValidation:
    """Tests for request body format validation."""

    @pytest.mark.api
    def test_create_task_without_content_type_returns_415(
        self, client, db_session
    ):
        """
        Test that request without Content-Type header returns 415.

        HTTP 415 Unsupported Media Type is the correct response when
        the server cannot process the request due to an unsupported
        media type (missing or wrong Content-Type header).
        """
        # Act
        response = client.post("/api/tasks")

        # Assert - 415 is correct for missing Content-Type
        assert response.status_code == 415

    @pytest.mark.api
    def test_create_task_with_invalid_json_returns_400(
        self, client, db_session, api_headers
    ):
        """
        Test that malformed JSON is rejected.
        """
        # Act
        response = client.post(
            "/api/tasks",
            data="{ invalid json }",
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400

    @pytest.mark.api
    def test_update_task_without_content_type_returns_415(
        self, client, db_session, sample_task
    ):
        """
        Test that PUT request without Content-Type header returns 415.
        """
        # Act
        response = client.put(f"/api/tasks/{sample_task.id}")

        # Assert - 415 is correct for missing Content-Type
        assert response.status_code == 415


class TestEstimatedMinutesValidation:
    """Tests for task estimated_minutes field validation."""

    @pytest.mark.api
    def test_create_task_with_valid_estimated_minutes_succeeds(
        self, client, db_session, api_headers
    ):
        """
        Test that valid estimated_minutes is accepted.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "estimated_minutes": 30
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["estimated_minutes"] == 30

    @pytest.mark.api
    def test_create_task_with_null_estimated_minutes_succeeds(
        self, client, db_session, api_headers
    ):
        """
        Test that null estimated_minutes is accepted (optional field).
        """
        # Arrange
        data = {
            "title": "Test Task",
            "estimated_minutes": None
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["estimated_minutes"] is None

    @pytest.mark.api
    def test_create_task_without_estimated_minutes_defaults_to_none(
        self, client, db_session, api_headers
    ):
        """
        Test that omitting estimated_minutes defaults to None.
        """
        # Arrange
        data = {"title": "Test Task"}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["estimated_minutes"] is None

    @pytest.mark.api
    @pytest.mark.parametrize("invalid_value", [
        0,          # Zero is not valid (must be positive)
        -1,         # Negative value
        -100,       # Large negative value
        "thirty",   # String instead of int
        3.5,        # Float instead of int
    ])
    def test_create_task_with_invalid_estimated_minutes_returns_400(
        self, client, db_session, api_headers, invalid_value
    ):
        """
        Test that invalid estimated_minutes values are rejected.

        Boundary: Must be a positive integer (>= 1).
        """
        # Arrange
        data = {
            "title": "Test Task",
            "estimated_minutes": invalid_value
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        error_data = json.loads(response.data)
        assert "error" in error_data

    @pytest.mark.api
    def test_create_task_with_minimum_valid_estimated_minutes(
        self, client, db_session, api_headers
    ):
        """
        Test boundary: minimum valid value is 1 minute.
        """
        # Arrange
        data = {
            "title": "Test Task",
            "estimated_minutes": 1
        }

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result["estimated_minutes"] == 1

    @pytest.mark.api
    def test_update_task_estimated_minutes(
        self, client, db_session, sample_task, api_headers
    ):
        """
        Test updating estimated_minutes on an existing task.
        """
        # Arrange
        update_data = {"estimated_minutes": 60}

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps(update_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["estimated_minutes"] == 60


class TestIdValidation:
    """Tests for task ID validation in URLs."""

    @pytest.mark.api
    def test_get_task_with_negative_id_returns_404(
        self, client, db_session
    ):
        """
        Test that negative task ID returns 404.

        Note: Flask will match the route but the task won't exist.
        """
        # Act
        response = client.get("/api/tasks/-1")

        # Assert
        assert response.status_code == 404

    @pytest.mark.api
    def test_get_task_with_zero_id_returns_404(
        self, client, db_session
    ):
        """
        Test that task ID of 0 returns 404.

        IDs typically start at 1 in most databases.
        """
        # Act
        response = client.get("/api/tasks/0")

        # Assert
        assert response.status_code == 404

    @pytest.mark.api
    def test_get_task_with_very_large_id_returns_404(
        self, client, db_session
    ):
        """
        Test that very large task ID returns 404.
        """
        # Act
        response = client.get("/api/tasks/999999999")

        # Assert
        assert response.status_code == 404
