"""
CRUD-heavy Locust scenario.

Defines :class:`TaskCrudUser`, which exercises the complete
create / read / update / delete lifecycle of the task service.  Unlike
:class:`~tests.performance.scenarios.mixed.MixedTrafficUser`, this
scenario includes ``DELETE`` operations and omits auth-verification
traffic, making it a focused stress test for the task service alone.

The weight distribution (total weight 10) is:

- **70 % reads** — list tasks (5) + get single task (2)
- **20 % writes** — create task (1) + update task (1)
- **10 % deletes** — delete task (1), with automatic pool replenishment

Key Concepts Demonstrated:
- Full CRUD coverage including destructive operations
- Pool-stable delete pattern (delete + immediate re-create) to prevent
  cascading ``404`` errors in subsequent iterations
"""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.scenarios.base import TaskWorkflowUser


@tag("crud")
class TaskCrudUser(TaskWorkflowUser):
    """
    Exercise task CRUD under sustained mixed operations.

    Shares the same think-time (1–3 s) as
    :class:`~tests.performance.scenarios.mixed.MixedTrafficUser` so
    that latency comparisons between scenarios are apples-to-apples.
    """

    wait_time = between(1, 3)

    # ---- 70 % reads (weight 5 + 2 out of 10) -----------------------

    @task(5)
    def list_tasks(self) -> None:
        """Fetch the full task list."""
        self._list_tasks()

    @task(2)
    def get_single_task(self) -> None:
        """Retrieve one task by ID."""
        self._get_single_task()

    # ---- 20 % writes (weight 1 + 1 out of 10) ----------------------

    @task(1)
    def create_task(self) -> None:
        """Add a new task with a randomised payload."""
        self._create_task()

    @task(1)
    def update_task(self) -> None:
        """Partially update an existing task."""
        self._update_task()

    # ---- 10 % deletes (weight 1 out of 10) -------------------------

    @task(1)
    def delete_task(self) -> None:
        """Remove a task and create a replacement to keep the pool stable."""
        self._delete_task()
