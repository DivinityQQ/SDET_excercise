"""
Shared abstract Locust user classes for performance scenarios.

Provides two layers of abstraction that concrete scenarios build on:

1. :class:`AuthenticatedApiUser` — handles the register → login
   lifecycle so that every virtual user starts with a valid JWT.
2. :class:`TaskWorkflowUser` — adds a local pool of task IDs and
   reusable CRUD primitives (list, get, create, update, delete).

Concrete user classes (e.g.
:class:`~tests.performance.scenarios.mixed.MixedTrafficUser`) only need
to declare Locust ``@task`` methods that delegate to the ``_`` prefixed
helpers defined here.

Key Concepts Demonstrated:
- Abstract Locust base classes for DRY scenario authoring
- ``catch_response=True`` for in-band response validation without
  inflating Locust's error statistics on parse failures
- Self-healing task pool that auto-replenishes when empty
"""

from __future__ import annotations

import random
from typing import Any

from locust import HttpUser
from locust.exception import StopUser

from tests.performance.helpers import (
    auth_header,
    login_user,
    random_task_payload,
    random_task_update_payload,
    register_user,
    unique_user_identity,
)


class AuthenticatedApiUser(HttpUser):
    """
    Base user that registers and logs in once at startup.

    Mirrors the real-world flow where a person creates an account, logs
    in, and then performs all subsequent actions with a bearer token.
    ``abstract = True`` tells Locust not to spawn this class directly —
    only its concrete subclasses.

    Attributes:
        username: Display name created during ``on_start``.
        email: Email address created during ``on_start``.
        password: Plain-text password (fixed across all virtual users).
        token: JWT obtained from the auth service after login.
        headers: Pre-built header dict (``Authorization``,
            ``Content-Type``, ``Accept``) reused for every request.
    """

    abstract = True

    username: str
    email: str
    password: str
    token: str
    headers: dict[str, str]

    def on_start(self) -> None:
        """Register a unique account, log in, and store the JWT."""
        self.username, self.email, self.password = unique_user_identity()

        if not register_user(
            self.client,
            username=self.username,
            email=self.email,
            password=self.password,
        ):
            raise StopUser("Registration failed")

        token = login_user(
            self.client,
            username=self.username,
            password=self.password,
        )
        if token is None:
            raise StopUser("Login failed")

        self.token = token
        self.headers = auth_header(self.token)


class TaskWorkflowUser(AuthenticatedApiUser):
    """
    Base user with common task CRUD actions and local task pool.

    Extends :class:`AuthenticatedApiUser` with a per-user ``task_ids``
    list that is seeded at startup and maintained as tasks are created
    or deleted.  This ensures that read and update operations always
    target tasks the user actually owns, avoiding artificial ``404``
    responses that would skew error rates.

    Attributes:
        min_seed_tasks: Number of tasks created during ``on_start`` to
            bootstrap the pool.
        task_ids: Running list of task primary keys owned by this
            virtual user.
    """

    abstract = True
    min_seed_tasks = 3

    task_ids: list[int]

    def on_start(self) -> None:
        """Authenticate and pre-populate the local task pool."""
        super().on_start()
        self.task_ids = []
        self._seed_tasks(self.min_seed_tasks)

    def _seed_tasks(self, amount: int) -> None:
        """Create *amount* tasks so reads/updates have data from the start."""
        for _ in range(amount):
            task_id = self._create_task_internal()
            if task_id is not None:
                self.task_ids.append(task_id)

    def _create_task_internal(self) -> int | None:
        """POST a new task and return its server-assigned ID, or ``None``."""
        with self.client.post(
            "/api/tasks",
            json=random_task_payload(),
            headers=self.headers,
            name="/api/tasks [POST]",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"Expected 201, got {response.status_code}")
                return None

            body = _safe_json(response)
            task_id = body.get("id")
            if not isinstance(task_id, int):
                response.failure("Create response missing integer id")
                return None

            response.success()
            return task_id

    def _pick_task_id(self) -> int | None:
        """
        Return a random task ID from the pool, auto-creating one if empty.

        This self-healing behaviour keeps the pool non-empty even after
        a burst of deletes, preventing downstream actions from silently
        becoming no-ops.
        """
        if not self.task_ids:
            task_id = self._create_task_internal()
            if task_id is not None:
                self.task_ids.append(task_id)

        if not self.task_ids:
            return None

        return random.choice(self.task_ids)

    def _list_tasks(self) -> None:
        """GET the full task list and validate the response shape."""
        with self.client.get(
            "/api/tasks",
            headers=self.headers,
            name="/api/tasks [GET]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            body = _safe_json(response)
            if not isinstance(body.get("tasks"), list):
                response.failure("List response missing tasks list")
                return

            response.success()

    def _get_single_task(self) -> None:
        """GET one task by ID and verify the returned ID matches."""
        task_id = self._pick_task_id()
        if task_id is None:
            return

        with self.client.get(
            f"/api/tasks/{task_id}",
            headers=self.headers,
            name="/api/tasks/[id] [GET]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            body = _safe_json(response)
            if body.get("id") != task_id:
                response.failure("Fetched task id does not match request")
                return

            response.success()

    def _create_task(self) -> None:
        """Create a task and add its ID to the local pool."""
        task_id = self._create_task_internal()
        if task_id is not None:
            self.task_ids.append(task_id)

    def _update_task(self) -> None:
        """PUT a partial update to a randomly chosen owned task."""
        task_id = self._pick_task_id()
        if task_id is None:
            return

        payload = random_task_update_payload()
        with self.client.put(
            f"/api/tasks/{task_id}",
            json=payload,
            headers=self.headers,
            name="/api/tasks/[id] [PUT]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            body = _safe_json(response)
            if body.get("id") != task_id:
                response.failure("Update response id mismatch")
                return

            response.success()

    def _delete_task(self) -> None:
        """
        Delete a task and immediately create a replacement.

        The replacement keeps the pool size roughly constant so that
        subsequent reads and updates continue to hit valid IDs rather
        than producing a growing stream of ``404`` errors.
        """
        task_id = self._pick_task_id()
        if task_id is None:
            return

        with self.client.delete(
            f"/api/tasks/{task_id}",
            headers=self.headers,
            name="/api/tasks/[id] [DELETE]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            if task_id in self.task_ids:
                self.task_ids.remove(task_id)

            replacement_task_id = self._create_task_internal()
            if replacement_task_id is not None:
                self.task_ids.append(replacement_task_id)

            response.success()

    def _verify_token(self) -> None:
        """Hit the auth-verify endpoint and validate the returned claims."""
        with self.client.get(
            "/api/auth/verify",
            headers=self.headers,
            name="/api/auth/verify [GET]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            body = _safe_json(response)
            if not isinstance(body.get("user_id"), int):
                response.failure("Verify response missing user_id")
                return
            if body.get("username") != self.username:
                response.failure("Verify response username mismatch")
                return

            response.success()


def _safe_json(response: Any) -> dict[str, Any]:
    """Return response JSON as a dict, or ``{}`` if parsing fails."""
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data
    return {}
