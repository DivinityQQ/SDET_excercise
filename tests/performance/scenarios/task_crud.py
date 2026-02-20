"""CRUD-heavy Locust scenario."""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.scenarios.base import TaskWorkflowUser


@tag("crud")
class TaskCrudUser(TaskWorkflowUser):
    """Exercise task CRUD under sustained mixed operations."""

    wait_time = between(1, 3)

    @task(5)
    def list_tasks(self) -> None:
        self._list_tasks()

    @task(2)
    def get_single_task(self) -> None:
        self._get_single_task()

    @task(1)
    def create_task(self) -> None:
        self._create_task()

    @task(1)
    def update_task(self) -> None:
        self._update_task()

    @task(1)
    def delete_task(self) -> None:
        self._delete_task()
