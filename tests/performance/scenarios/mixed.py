"""
Production-like mixed-traffic Locust scenario.

Defines :class:`MixedTrafficUser`, the default scenario used in CI
performance gates.  The traffic mix approximates a typical web
application where the vast majority of requests are reads, with
occasional writes and periodic auth checks.

The weight distribution (total weight 10) is:

- **70 % reads** — list tasks (5) + get single task (2)
- **20 % writes** — create task (1) + update task (1)
- **10 % auth** — token verification (1)

Key Concepts Demonstrated:
- Locust ``@task(weight)`` for proportional action selection
- Read-heavy ratio that mirrors real-world usage patterns
- Composition over inheritance — thin class that delegates to
  :class:`~tests.performance.scenarios.base.TaskWorkflowUser` helpers
"""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.scenarios.base import TaskWorkflowUser


@tag("mixed")
class MixedTrafficUser(TaskWorkflowUser):
    """
    Read-heavy scenario with writes and auth checks mixed in.

    This is the closest approximation to real user traffic and is the
    scenario used by the CI performance gate (``--tags mixed``).  Each
    virtual user waits 1–3 seconds between actions to simulate human
    think-time.
    """

    wait_time = between(1, 3)

    # ---- 70 % reads (weight 5 + 2 out of 10) -----------------------

    @task(5)
    def list_tasks(self) -> None:
        """Browse the task list — the most common user action."""
        self._list_tasks()

    @task(2)
    def get_single_task(self) -> None:
        """Open a single task detail page."""
        self._get_single_task()

    # ---- 20 % writes (weight 1 + 1 out of 10) ----------------------

    @task(1)
    def create_task(self) -> None:
        """Add a new task with randomised fields."""
        self._create_task()

    @task(1)
    def update_task(self) -> None:
        """Edit one field on an existing task."""
        self._update_task()

    # ---- 10 % auth checks (weight 1 out of 10) ---------------------

    @task(1)
    def verify_token(self) -> None:
        """Validate the current JWT, simulating a session heartbeat."""
        self._verify_token()
