"""
Helper utilities for Locust performance scenarios.

Provides the building blocks that every Locust user class relies on:
credential generation, authentication workflows, and randomised payload
factories.  Keeping these in a shared module avoids duplication across
scenario files and makes it easy to adjust data-generation strategies
in one place.

Key Concepts Demonstrated:
- Collision-free identity generation using timestamp + random suffix
- Reusable auth helpers that wrap Locust's ``catch_response`` protocol
- Randomised payloads to defeat server-side caching and exercise
  varied code paths
"""

from __future__ import annotations

import random
import string
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from locust.clients import HttpSession


def _safe_json(response: Any) -> dict[str, Any]:
    """
    Return response JSON as dict, or an empty dict if parsing fails.

    Locust responses may contain non-JSON bodies (e.g. on 5xx errors or
    gateway timeouts).  Using this wrapper prevents ``ValueError`` from
    propagating into task methods where it would abort the virtual user.

    Args:
        response: A Locust/requests ``Response`` object.

    Returns:
        The parsed JSON body as a dictionary, or ``{}`` if parsing fails
        or the top-level value is not a dict.
    """
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data
    return {}


def register_user(client: HttpSession, *, username: str, email: str, password: str) -> bool:
    """
    Register a user through the real auth endpoint.

    Each Locust virtual user calls this once during ``on_start`` so that
    every simulated user owns a distinct account — matching the
    single-tenant model of the application.

    Args:
        client: The Locust HTTP session (auto-manages cookies/connection
            pooling).
        username: Desired username for the new account.
        email: Email address for the new account.
        password: Plain-text password (hashed server-side).

    Returns:
        ``True`` if the server responded with ``201 Created`` and a valid
        user payload, ``False`` otherwise.
    """
    with client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
        name="/api/auth/register [POST]",
        catch_response=True,
    ) as response:
        if response.status_code != 201:
            response.failure(f"Expected 201, got {response.status_code}")
            return False

        body = _safe_json(response)
        user_data = body.get("user")
        if not isinstance(user_data, dict) or not user_data.get("id"):
            response.failure("Registration response missing user payload")
            return False

        response.success()
        return True


def login_user(client: HttpSession, *, username: str, password: str) -> str | None:
    """
    Log in and return a bearer token.

    Called once during ``on_start`` to obtain a JWT, and potentially
    again by scenarios that simulate token refresh (e.g.
    :class:`~tests.performance.scenarios.auth_storm.AuthStormUser`).

    Args:
        client: The Locust HTTP session.
        username: Registered username.
        password: Plain-text password.

    Returns:
        The JWT string on success, or ``None`` if the login request
        failed or the response lacked a token.
    """
    with client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        name="/api/auth/login [POST]",
        catch_response=True,
    ) as response:
        if response.status_code != 200:
            response.failure(f"Expected 200, got {response.status_code}")
            return None

        body = _safe_json(response)
        token = body.get("token")
        if not isinstance(token, str) or not token:
            response.failure("Login response missing token")
            return None

        response.success()
        return token


def auth_header(token: str) -> dict[str, str]:
    """
    Build standard bearer auth headers for API requests.

    Returns a header dict that includes ``Authorization``,
    ``Content-Type``, and ``Accept`` — the minimum set the API gateway
    expects for authenticated JSON requests.

    Args:
        token: A valid JWT string.

    Returns:
        A dictionary suitable for passing as ``headers`` to Locust
        request methods.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def unique_user_identity() -> tuple[str, str, str]:
    """
    Generate unique credentials to avoid collisions across runs.

    Combines a millisecond timestamp with a short random suffix so that
    parallel Locust workers (or back-to-back CI runs) never produce
    duplicate usernames.

    Returns:
        A ``(username, email, password)`` tuple.  The password is a
        fixed string — security of test accounts is not a concern.
    """
    ts = int(time.time() * 1000)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"perf_{ts}_{suffix}"
    email = f"{username}@example.com"
    password = "PerfPass123!"
    return username, email, password


def random_status() -> str:
    """Pick a random task status value from those the API accepts."""
    return random.choice(["pending", "in_progress", "completed"])


def random_task_payload() -> dict[str, Any]:
    """
    Build a valid task-create payload with small randomised variance.

    Every field is populated with a random but schema-valid value so
    that the server processes a realistic spread of inputs rather than
    hitting the same cached/optimised path repeatedly.

    Returns:
        A JSON-serialisable dictionary matching the task-create schema.
    """
    now_utc = datetime.now(timezone.utc)
    due_date = (now_utc + timedelta(days=random.randint(1, 14))).isoformat()

    title_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return {
        "title": f"Perf task {title_suffix}",
        "description": "Created by Locust performance test",
        "priority": random.choice(["low", "medium", "high"]),
        "status": random_status(),
        "estimated_minutes": random.randint(5, 180),
        "due_date": due_date,
    }


def random_task_update_payload() -> dict[str, Any]:
    """
    Build a valid task-update payload.

    Unlike creates, real updates usually touch only one or two fields at
    a time.  This function mirrors that pattern by selecting a single
    random field from the full payload.

    Returns:
        A JSON-serialisable dictionary containing exactly one mutable
        task field.
    """
    base = random_task_payload()

    # Each candidate is a single-field dict; only one is chosen so that
    # the update exercises the partial-update code path on the server.
    candidates: list[dict[str, Any]] = [
        {"title": base["title"]},
        {"description": f"Updated at {datetime.now(timezone.utc).isoformat()}"},
        {"priority": base["priority"]},
        {"status": base["status"]},
        {"estimated_minutes": base["estimated_minutes"]},
    ]
    return random.choice(candidates)
