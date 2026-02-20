"""
Authentication-heavy Locust scenario.

Defines :class:`AuthStormUser`, a specialised user class that hammers
the authentication endpoints.  Useful for stress-testing JWT
verification throughput and the login code path (password hashing,
token issuance) in isolation from the task service.

The weight distribution (total weight 10) is:

- **70 % token verification** — lightweight GET that validates an
  existing JWT.
- **30 % re-login** — full credential exchange that triggers server-side
  password hashing and a fresh JWT signature.  Replacing the stored
  token on each successful re-login mirrors clients that implement
  token rotation.

Key Concepts Demonstrated:
- Targeted scenario for isolating a single service under load
- Shorter think-time (0.5–1.5 s) to generate higher per-user RPS than
  the mixed scenario
- Token refresh pattern via ``login_again``
"""

from __future__ import annotations

from locust import between, tag, task

from tests.performance.helpers import auth_header, login_user
from tests.performance.scenarios.base import AuthenticatedApiUser


@tag("auth")
class AuthStormUser(AuthenticatedApiUser):
    """
    Generate auth/verification traffic against the gateway.

    Inherits directly from :class:`AuthenticatedApiUser` rather than
    :class:`TaskWorkflowUser` because it never touches the task service
    — keeping the load focused on the auth service alone.
    """

    # Shorter think-time than the mixed scenario to push higher RPS
    # against the auth service.
    wait_time = between(0.5, 1.5)

    @task(7)
    def verify_token(self) -> None:
        """Validate the current JWT and assert the returned claims."""
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
        """Re-authenticate and replace the stored token, simulating rotation."""
        token = login_user(
            self.client,
            username=self.username,
            password=self.password,
        )
        if token is None:
            return

        self.token = token
        self.headers = auth_header(self.token)
