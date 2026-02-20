"""Production-like mixed-traffic Locust scenario."""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.scenarios.base import TaskWorkflowUser


@tag("mixed")
class MixedTrafficUser(TaskWorkflowUser):
    """Read-heavy scenario with writes and auth checks mixed in."""

    wait_time = between(1, 3)

    # 70% reads: 5 + 2 out of total weight 10
    @task(5)
    def list_tasks(self) -> None:
        self._list_tasks()

    @task(2)
    def get_single_task(self) -> None:
        self._get_single_task()

    # 20% writes: 1 + 1 out of total weight 10
    @task(1)
    def create_task(self) -> None:
        self._create_task()

    @task(1)
    def update_task(self) -> None:
        self._update_task()

    # 10% auth checks: 1 out of total weight 10
    @task(1)
    def verify_token(self) -> None:
        self._verify_token()
