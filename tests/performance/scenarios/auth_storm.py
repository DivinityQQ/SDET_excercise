"""Authentication-heavy Locust scenario."""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.helpers import auth_header, login_user
from tests.performance.scenarios.base import AuthenticatedApiUser


@tag("auth")
class AuthStormUser(AuthenticatedApiUser):
    """Generate auth/verification traffic against the gateway."""

    wait_time = between(0.5, 1.5)

    @task(7)
    def verify_token(self) -> None:
        with self.client.get(
            "/api/auth/verify",
            headers=self.headers,
            name="/api/auth/verify [GET]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return

            try:
                payload = response.json()
            except ValueError:
                response.failure("Verify response is not valid JSON")
                return

            if not isinstance(payload, dict):
                response.failure("Verify response JSON is not an object")
                return
            if not isinstance(payload.get("user_id"), int):
                response.failure("Verify response missing user_id")
                return
            if payload.get("username") != self.username:
                response.failure("Verify response username mismatch")
                return

            response.success()

    @task(3)
    def login_again(self) -> None:
        token = login_user(
            self.client,
            username=self.username,
            password=self.password,
        )
        if token is None:
            return

        self.token = token
        self.headers = auth_header(self.token)
