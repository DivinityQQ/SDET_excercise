"""Shared abstract Locust user classes for performance scenarios."""

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
    """Base user that registers and logs in once at startup."""

    abstract = True

    username: str
    email: str
    password: str
    token: str
    headers: dict[str, str]

    def on_start(self) -> None:
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
    """Base user with common task CRUD actions and local task pool."""

    abstract = True
    min_seed_tasks = 3

    task_ids: list[int]

    def on_start(self) -> None:
        super().on_start()
        self.task_ids = []
        self._seed_tasks(self.min_seed_tasks)

    def _seed_tasks(self, amount: int) -> None:
        for _ in range(amount):
            task_id = self._create_task_internal()
            if task_id is not None:
                self.task_ids.append(task_id)

    def _create_task_internal(self) -> int | None:
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
        if not self.task_ids:
            task_id = self._create_task_internal()
            if task_id is not None:
                self.task_ids.append(task_id)

        if not self.task_ids:
            return None

        return random.choice(self.task_ids)

    def _list_tasks(self) -> None:
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
        task_id = self._create_task_internal()
        if task_id is not None:
            self.task_ids.append(task_id)

    def _update_task(self) -> None:
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

            # Keep pool size stable so user behavior remains realistic.
            if task_id in self.task_ids:
                self.task_ids.remove(task_id)

            replacement_task_id = self._create_task_internal()
            if replacement_task_id is not None:
                self.task_ids.append(replacement_task_id)

            response.success()

    def _verify_token(self) -> None:
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
    """Return response JSON as dict, or an empty dict if parsing fails."""
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data
    return {}
