"""
API CRUD Tests for Task endpoints.

This module tests the basic Create, Read, Update, Delete operations
for the /api/tasks endpoints. Each test follows the AAA pattern:
- Arrange: Set up test data and preconditions
- Act: Perform the action being tested
- Assert: Verify the expected outcomes

Key SDET Concepts Demonstrated:
- Testing HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Status code validation
- Response body validation
- Testing with fixtures
- Test isolation
"""

import pytest
import json
from app.models import TaskStatus, TaskPriority

pytestmark = pytest.mark.integration


class TestGetTasks:
    """Tests for GET /api/tasks endpoint."""

    def test_get_tasks_returns_empty_list_when_no_tasks(
        self, client, db_session
    ):
        """
        Test that GET /api/tasks returns empty list when no tasks exist.

        Arrange: Ensure database is empty (handled by db_session fixture)
        Act: Send GET request to /api/tasks
        Assert: Response has 200 status and empty tasks list
        """
        # Act
        response = client.get("/api/tasks")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["tasks"] == []
        assert data["count"] == 0

    def test_get_tasks_returns_all_tasks(
        self, client, db_session, multiple_tasks
    ):
        """
        Test that GET /api/tasks returns all existing tasks.

        Arrange: Create multiple tasks using fixture
        Act: Send GET request to /api/tasks
        Assert: Response contains all created tasks
        """
        # Arrange - multiple_tasks fixture creates 4 tasks

        # Act
        response = client.get("/api/tasks")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["count"] == 4
        assert len(data["tasks"]) == 4

    def test_get_tasks_with_status_filter(
        self, client, db_session, multiple_tasks
    ):
        """
        Test filtering tasks by status.

        Arrange: Create tasks with different statuses
        Act: Send GET request with status query parameter
        Assert: Only tasks with matching status are returned
        """
        # Act
        response = client.get("/api/tasks?status=in_progress")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["count"] == 2  # Two in_progress tasks in fixture
        for task in data["tasks"]:
            assert task["status"] == "in_progress"

    def test_get_tasks_with_priority_filter(
        self, client, db_session, multiple_tasks
    ):
        """
        Test filtering tasks by priority.

        Arrange: Create tasks with different priorities
        Act: Send GET request with priority query parameter
        Assert: Only tasks with matching priority are returned
        """
        # Act
        response = client.get("/api/tasks?priority=high")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["count"] == 2  # Two high priority tasks in fixture
        for task in data["tasks"]:
            assert task["priority"] == "high"


class TestGetTask:
    """Tests for GET /api/tasks/<id> endpoint."""

    def test_get_task_returns_task_by_id(
        self, client, db_session, sample_task
    ):
        """
        Test that GET /api/tasks/<id> returns the correct task.

        Arrange: Create a sample task
        Act: Send GET request with task ID
        Assert: Response contains correct task data
        """
        # Act
        response = client.get(f"/api/tasks/{sample_task.id}")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == sample_task.id
        assert data["title"] == sample_task.title
        assert data["description"] == sample_task.description

    def test_get_task_returns_404_for_nonexistent_task(
        self, client, db_session
    ):
        """
        Test that GET /api/tasks/<id> returns 404 for non-existent task.

        Arrange: Ensure task with ID 99999 doesn't exist
        Act: Send GET request with non-existent ID
        Assert: Response has 404 status with error message
        """
        # Act
        response = client.get("/api/tasks/99999")

        # Assert
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert "not found" in data["error"].lower()


class TestCreateTask:
    """Tests for POST /api/tasks endpoint."""

    @pytest.mark.smoke
    def test_create_task_with_valid_data(
        self, client, db_session, valid_task_data, api_headers
    ):
        """
        Test creating a task with all valid fields.

        Arrange: Prepare valid task data
        Act: Send POST request with task data
        Assert: Task is created with 201 status and correct data
        """
        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == valid_task_data["title"]
        assert data["description"] == valid_task_data["description"]
        assert data["status"] == valid_task_data["status"]
        assert data["priority"] == valid_task_data["priority"]
        assert "id" in data
        assert data["id"] is not None

    def test_create_task_with_minimal_data(
        self, client, db_session, minimal_task_data, api_headers
    ):
        """
        Test creating a task with only required fields.

        Arrange: Prepare minimal task data (only title)
        Act: Send POST request with minimal data
        Assert: Task is created with default values for optional fields
        """
        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(minimal_task_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == minimal_task_data["title"]
        assert data["status"] == TaskStatus.PENDING.value  # Default
        assert data["priority"] == TaskPriority.MEDIUM.value  # Default

    def test_create_task_without_title_returns_400(
        self, client, db_session, api_headers
    ):
        """
        Test that creating a task without title returns 400.

        Arrange: Prepare task data without required title field
        Act: Send POST request with invalid data
        Assert: Response has 400 status with validation error
        """
        # Arrange
        invalid_data = {"description": "Task without title"}

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(invalid_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "title" in data["error"].lower()


class TestUpdateTask:
    """Tests for PUT /api/tasks/<id> endpoint."""

    def test_update_task_with_valid_data(
        self, client, db_session, sample_task, api_headers
    ):
        """
        Test updating a task with valid data.

        Arrange: Create a sample task
        Act: Send PUT request with updated data
        Assert: Task is updated and changes are reflected
        """
        # Arrange
        updated_data = {
            "title": "Updated Title",
            "description": "Updated description",
            "status": TaskStatus.COMPLETED.value,
            "priority": TaskPriority.HIGH.value
        }

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps(updated_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == updated_data["title"]
        assert data["description"] == updated_data["description"]
        assert data["status"] == updated_data["status"]
        assert data["priority"] == updated_data["priority"]

    def test_update_task_partial_data(
        self, client, db_session, sample_task, api_headers
    ):
        """
        Test updating only some fields of a task.

        Arrange: Create a task with known values
        Act: Send PUT request updating only title
        Assert: Title is updated, other fields unchanged
        """
        # Arrange
        original_status = sample_task.status
        partial_update = {"title": "Partially Updated Title"}

        # Act
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps(partial_update),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == partial_update["title"]
        assert data["status"] == original_status  # Unchanged

    def test_update_nonexistent_task_returns_404(
        self, client, db_session, api_headers
    ):
        """
        Test that updating a non-existent task returns 404.

        Arrange: Ensure task ID 99999 doesn't exist
        Act: Send PUT request to non-existent task
        Assert: Response has 404 status
        """
        # Arrange
        update_data = {"title": "Won't Be Updated"}

        # Act
        response = client.put(
            "/api/tasks/99999",
            data=json.dumps(update_data),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 404


class TestDeleteTask:
    """Tests for DELETE /api/tasks/<id> endpoint."""

    def test_delete_task_removes_task(
        self, client, db_session, task_factory
    ):
        """
        Test that DELETE /api/tasks/<id> removes the task.

        Arrange: Create a task to delete
        Act: Send DELETE request
        Assert: Task is deleted (subsequent GET returns 404)
        """
        # Arrange
        task = task_factory(title="Task to Delete")
        task_id = task.id

        # Act
        response = client.delete(f"/api/tasks/{task_id}")

        # Assert
        assert response.status_code == 200

        # Verify task is actually deleted
        get_response = client.get(f"/api/tasks/{task_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_task_returns_404(
        self, client, db_session
    ):
        """
        Test that deleting a non-existent task returns 404.

        Arrange: Ensure task ID 99999 doesn't exist
        Act: Send DELETE request to non-existent task
        Assert: Response has 404 status
        """
        # Act
        response = client.delete("/api/tasks/99999")

        # Assert
        assert response.status_code == 404


class TestUpdateTaskStatus:
    """Tests for PATCH /api/tasks/<id>/status endpoint."""

    def test_update_status_changes_only_status(
        self, client, db_session, sample_task, api_headers
    ):
        """
        Test that PATCH /api/tasks/<id>/status only updates status.

        Arrange: Create a task with known values
        Act: Send PATCH request with new status
        Assert: Status is updated, other fields unchanged
        """
        # Arrange
        original_title = sample_task.title
        new_status = TaskStatus.COMPLETED.value

        # Act
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": new_status}),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == new_status
        assert data["title"] == original_title  # Unchanged

    @pytest.mark.parametrize("status", [
        TaskStatus.PENDING.value,
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.COMPLETED.value
    ])
    def test_update_status_accepts_valid_statuses(
        self, client, db_session, task_factory, api_headers, status
    ):
        """
        Test that all valid status values are accepted.

        This test demonstrates pytest parametrization - running
        the same test with different input values.

        Args:
            status: Valid status value to test.
        """
        # Arrange
        task = task_factory()

        # Act
        response = client.patch(
            f"/api/tasks/{task.id}/status",
            data=json.dumps({"status": status}),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == status

    def test_update_status_rejects_invalid_status(
        self, client, db_session, sample_task, api_headers
    ):
        """
        Test that invalid status values are rejected.

        Arrange: Create a task
        Act: Send PATCH with invalid status
        Assert: Response has 400 status with error message
        """
        # Act
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": "invalid_status"}),
            headers=api_headers
        )

        # Assert
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
