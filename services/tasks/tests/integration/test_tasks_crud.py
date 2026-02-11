"""Integration tests for authenticated task CRUD endpoints."""

from __future__ import annotations

import json

import pytest

from task_app.models import TaskPriority, TaskStatus

pytestmark = pytest.mark.integration


class TestGetTasks:
    def test_get_tasks_returns_empty_list_when_no_tasks(self, client, db_session, api_headers):
        response = client.get("/api/tasks", headers=api_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["tasks"] == []
        assert data["count"] == 0

    def test_get_tasks_returns_all_tasks_for_current_user(
        self, client, db_session, multiple_tasks, task_factory, api_headers
    ):
        task_factory(user_id=2, title="Other User Task")

        response = client.get("/api/tasks", headers=api_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 4
        assert len(data["tasks"]) == 4
        assert all(task["user_id"] == 1 for task in data["tasks"])

    def test_get_tasks_with_status_filter(self, client, db_session, multiple_tasks, api_headers):
        response = client.get("/api/tasks?status=in_progress", headers=api_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert all(task["status"] == "in_progress" for task in data["tasks"])

    def test_get_tasks_with_priority_filter(self, client, db_session, multiple_tasks, api_headers):
        response = client.get("/api/tasks?priority=high", headers=api_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert all(task["priority"] == "high" for task in data["tasks"])


class TestGetTask:
    def test_get_task_returns_task_by_id(self, client, db_session, sample_task, api_headers):
        response = client.get(f"/api/tasks/{sample_task.id}", headers=api_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == sample_task.id
        assert data["user_id"] == 1
        assert data["title"] == sample_task.title

    def test_get_task_returns_404_for_nonexistent_task(self, client, db_session, api_headers):
        response = client.get("/api/tasks/99999", headers=api_headers)
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_get_task_returns_404_for_other_users_task(
        self, client, db_session, task_factory, api_headers
    ):
        other_user_task = task_factory(user_id=2, title="Private Task")
        response = client.get(f"/api/tasks/{other_user_task.id}", headers=api_headers)
        assert response.status_code == 404


class TestCreateTask:
    def test_create_task_with_valid_data(
        self, client, db_session, valid_task_data, api_headers
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == valid_task_data["title"]
        assert data["user_id"] == 1

    def test_create_task_with_minimal_data(
        self, client, db_session, minimal_task_data, api_headers
    ):
        response = client.post(
            "/api/tasks",
            data=json.dumps(minimal_task_data),
            headers=api_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == minimal_task_data["title"]
        assert data["status"] == TaskStatus.PENDING.value
        assert data["priority"] == TaskPriority.MEDIUM.value

    def test_create_task_without_title_returns_400(self, client, db_session, api_headers):
        response = client.post(
            "/api/tasks",
            data=json.dumps({"description": "Task without title"}),
            headers=api_headers,
        )
        assert response.status_code == 400
        assert "title" in response.get_json()["error"].lower()


class TestUpdateTask:
    def test_update_task_with_valid_data(self, client, db_session, sample_task, api_headers):
        updated_data = {
            "title": "Updated Title",
            "description": "Updated description",
            "status": TaskStatus.COMPLETED.value,
            "priority": TaskPriority.HIGH.value,
        }
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps(updated_data),
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == TaskStatus.COMPLETED.value

    def test_update_task_partial_data(self, client, db_session, sample_task, api_headers):
        response = client.put(
            f"/api/tasks/{sample_task.id}",
            data=json.dumps({"title": "Partially Updated Title"}),
            headers=api_headers,
        )
        assert response.status_code == 200
        assert response.get_json()["title"] == "Partially Updated Title"

    def test_update_nonexistent_task_returns_404(self, client, db_session, api_headers):
        response = client.put(
            "/api/tasks/99999",
            data=json.dumps({"title": "Won't Be Updated"}),
            headers=api_headers,
        )
        assert response.status_code == 404

    def test_update_other_users_task_returns_404(
        self, client, db_session, task_factory, api_headers
    ):
        other_user_task = task_factory(user_id=2, title="Other Task")
        response = client.put(
            f"/api/tasks/{other_user_task.id}",
            data=json.dumps({"title": "Hacked"}),
            headers=api_headers,
        )
        assert response.status_code == 404


class TestDeleteTask:
    def test_delete_task_removes_task(self, client, db_session, task_factory, api_headers):
        task = task_factory(user_id=1, title="Task to Delete")
        task_id = task.id

        response = client.delete(f"/api/tasks/{task_id}", headers=api_headers)
        assert response.status_code == 200

        get_response = client.get(f"/api/tasks/{task_id}", headers=api_headers)
        assert get_response.status_code == 404

    def test_delete_nonexistent_task_returns_404(self, client, db_session, api_headers):
        response = client.delete("/api/tasks/99999", headers=api_headers)
        assert response.status_code == 404

    def test_delete_other_users_task_returns_404(
        self, client, db_session, task_factory, api_headers
    ):
        other_user_task = task_factory(user_id=2, title="Other Task")
        response = client.delete(f"/api/tasks/{other_user_task.id}", headers=api_headers)
        assert response.status_code == 404


class TestUpdateTaskStatus:
    def test_update_status_changes_only_status(self, client, db_session, sample_task, api_headers):
        original_title = sample_task.title
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": TaskStatus.COMPLETED.value}),
            headers=api_headers,
        )

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
        task = task_factory(user_id=1)
        response = client.patch(
            f"/api/tasks/{task.id}/status",
            data=json.dumps({"status": status}),
            headers=api_headers,
        )

        assert response.status_code == 200
        assert response.get_json()["status"] == status

    def test_update_status_rejects_invalid_status(self, client, db_session, sample_task, api_headers):
        response = client.patch(
            f"/api/tasks/{sample_task.id}/status",
            data=json.dumps({"status": "invalid_status"}),
            headers=api_headers,
        )

        assert response.status_code == 400
        assert "error" in response.get_json()

