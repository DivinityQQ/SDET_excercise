"""
Integration tests for authenticated task CRUD endpoints.

Covers the full create / read / update / delete lifecycle plus the
dedicated PATCH status endpoint. Each test class maps to a single HTTP
verb and exercises happy-path, not-found, and tenant-isolation scenarios.

Key SDET Concepts Demonstrated:
- REST CRUD testing (GET, POST, PUT, DELETE, PATCH)
- HTTP status-code verification (200, 201, 400, 404)
- Tenant isolation — users must never see or modify other users' tasks
- Parametrized tests for enum validation (valid statuses)
- Fixture composition (sample_task, multiple_tasks, task_factory)
"""

from __future__ import annotations

import json

import pytest

from services.tasks.task_app.models import TaskPriority, TaskStatus

pytestmark = pytest.mark.integration


class TestGetTasks:
    """Tests for the GET /api/tasks listing endpoint."""

    def test_get_tasks_returns_empty_list_when_no_tasks(self, client, db_session, api_headers):
        """Test that an empty database returns an empty task list with count 0."""
        # Arrange - provided by db_session (clean database)

        # Act
        response = client.get("/api/tasks", headers=api_headers)

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["tasks"] == []
        assert data["count"] == 0

    def test_get_tasks_returns_all_tasks_for_current_user(
        self, client, db_session, multiple_tasks, task_factory, api_headers
    ):
        """Test that only the authenticated user's tasks are returned, not other users'."""
        # Arrange
        task_factory(user_id=2, title="Other User Task")

        # Act
        response = client.get("/api/tasks", headers=api_headers)

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 4
        assert len(data["tasks"]) == 4
        assert all(task["user_id"] == 1 for task in data["tasks"])

    def test_get_tasks_with_status_filter(self, client, db_session, multiple_tasks, api_headers):
        """Test that the status query parameter filters results correctly."""
        # Arrange - provided by multiple_tasks fixture (2 in_progress tasks)

        # Act
        response = client.get("/api/tasks?status=in_progress", headers=api_headers)

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert all(task["status"] == "in_progress" for task in data["tasks"])

    def test_get_tasks_with_priority_filter(self, client, db_session, multiple_tasks, api_headers):
        """Test that the priority query parameter filters results correctly."""
        # Arrange - provided by multiple_tasks fixture (2 high-priority tasks)

        # Act
        response = client.get("/api/tasks?priority=high", headers=api_headers)

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert all(task["priority"] == "high" for task in data["tasks"])


class TestGetTask:
    """Tests for the GET /api/tasks/<id> detail endpoint."""

    def test_get_task_returns_task_by_id(self, client, db_session, sample_task, api_headers):
        """Test that a single task is returned when fetched by its ID."""
        # Arrange - provided by sample_task fixture

        # Act
        response = client.get(f"/api/tasks/{sample_task.id}", headers=api_headers)

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == sample_task.id
        assert data["user_id"] == 1
        assert data["title"] == sample_task.title

    def test_get_task_returns_404_for_nonexistent_task(self, client, db_session, api_headers):
        """Test that a request for a non-existent task ID returns 404."""
        # Arrange - no task with ID 99999

        # Act
        response = client.get("/api/tasks/99999", headers=api_headers)

        # Assert
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_get_task_returns_404_for_other_users_task(
        self, client, db_session, task_factory, api_headers
    ):
        """Test that accessing another user's task returns 404 (tenant isolation)."""
        # Arrange
        other_user_task = task_factory(user_id=2, title="Private Task")

        # Act
        response = client.get(f"/api/tasks/{other_user_task.id}", headers=api_headers)

        # Assert
        assert response.status_code == 404


class TestCreateTask:
    """Tests for the POST /api/tasks creation endpoint."""

    def test_create_task_with_valid_data(
        self, client, db_session, valid_task_data, api_headers
    ):
        """Test that a fully-populated payload creates a task and returns 201."""
        # Arrange - provided by valid_task_data fixture

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == valid_task_data["title"]
        assert data["user_id"] == 1

    def test_create_task_with_minimal_data(
        self, client, db_session, minimal_task_data, api_headers
    ):
        """Test that a title-only payload succeeds and applies default status/priority."""
        # Arrange - provided by minimal_task_data fixture

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(minimal_task_data),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == minimal_task_data["title"]
        assert data["status"] == TaskStatus.PENDING.value
        assert data["priority"] == TaskPriority.MEDIUM.value

    def test_create_task_without_title_returns_400(self, client, db_session, api_headers):
        """Test that omitting the required title field returns 400."""
        # Arrange
        payload = {"description": "Task without title"}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(payload),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400
        assert "title" in response.get_json()["error"].lower()


class TestUpdateTask:
    """Tests for the PUT /api/tasks/<id> full-update endpoint."""

    def test_update_task_with_valid_data(self, client, db_session, sample_task, api_headers):
        """Test that PUT with valid fields updates the task and returns 200."""
        # Arrange
        updated_data = {
            "title": "Updated Title",
            "description": "Updated description",
            "status": TaskStatus.COMPLETED.value,
            "priority": TaskPriority.HIGH.value,
        }

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps(updated_data),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == TaskStatus.COMPLETED.value

    def test_update_task_partial_data(self, client, db_session, sample_task, api_headers):
        """Test that sending only some fields updates those fields and leaves others intact."""
        # Arrange - provided by sample_task fixture

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps({"title": "Partially Updated Title"}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 200
        assert response.get_json()["title"] == "Partially Updated Title"

    def test_update_nonexistent_task_returns_404(self, client, db_session, api_headers):
        """Test that updating a non-existent task ID returns 404."""
        # Arrange - no task with ID 99999

        # Act
        response = client.put(
            "/api/tasks/99999",
            data=json.dumps({"title": "Won't Be Updated"}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 404

    def test_update_other_users_task_returns_404(
        self, client, db_session, task_factory, api_headers
    ):
        """Test that updating another user's task returns 404 (tenant isolation)."""
        # Arrange
        other_user_task = task_factory(user_id=2, title="Other Task")

        # Act
        response = client.put(
            f"/api/tasks/{other_user_task.id}",
            data=json.dumps({"title": "Hacked"}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 404


class TestDeleteTask:
    """Tests for the DELETE /api/tasks/<id> endpoint."""

    def test_delete_task_removes_task(self, client, db_session, task_factory, api_headers):
        """Test that DELETE removes the task and a subsequent GET returns 404."""
        # Arrange
        task = task_factory(user_id=1, title="Task to Delete")
        task_id = task.id

        # Act
        response = client.delete(f"/api/tasks/{task_id}", headers=api_headers)

        # Assert
        assert response.status_code == 200
        get_response = client.get(f"/api/tasks/{task_id}", headers=api_headers)
        assert get_response.status_code == 404

    def test_delete_nonexistent_task_returns_404(self, client, db_session, api_headers):
        """Test that deleting a non-existent task ID returns 404."""
        # Arrange - no task with ID 99999

        # Act
        response = client.delete("/api/tasks/99999", headers=api_headers)

        # Assert
        assert response.status_code == 404

    def test_delete_other_users_task_returns_404(
        self, client, db_session, task_factory, api_headers
    ):
        """Test that deleting another user's task returns 404 (tenant isolation)."""
        # Arrange
        other_user_task = task_factory(user_id=2, title="Other Task")

        # Act
        response = client.delete(f"/api/tasks/{other_user_task.id}", headers=api_headers)

        # Assert
        assert response.status_code == 404


class TestUpdateTaskStatus:
    """Tests for the PATCH /api/tasks/<id>/status status-only endpoint."""

    def test_update_status_changes_only_status(self, client, db_session, sample_task, api_headers):
        """Test that PATCH /status changes the status without altering other fields."""
        # Arrange
        original_title = sample_task.title

        # Act
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": TaskStatus.COMPLETED.value}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == TaskStatus.COMPLETED.value
        assert data["title"] == original_title

    @pytest.mark.parametrize(
        "status",
        [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value, TaskStatus.COMPLETED.value],
    )
    def test_update_status_accepts_valid_statuses(
        self, client, db_session, task_factory, api_headers, status
    ):
        """Test that each valid status enum value is accepted by the PATCH endpoint."""
        # Arrange — parametrized 'status' represents each valid TaskStatus value
        task = task_factory(user_id=1)

        # Act
        response = client.patch(
            f"/api/tasks/{task.id}/status",
            data=json.dumps({"status": status}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 200
        assert response.get_json()["status"] == status

    def test_update_status_rejects_invalid_status(self, client, db_session, sample_task, api_headers):
        """Test that an unrecognized status value returns 400."""
        # Arrange - provided by sample_task fixture

        # Act
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": "invalid_status"}),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()
