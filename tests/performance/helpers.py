"""Helper utilities for Locust performance scenarios."""

from __future__ import annotations

import random
import string
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from locust.clients import HttpSession


def _safe_json(response: Any) -> dict[str, Any]:
    """Return response JSON as dict, or an empty dict if parsing fails."""
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data
    return {}


def register_user(client: HttpSession, *, username: str, email: str, password: str) -> bool:
    """Register a user through the real auth endpoint."""
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
    """Log in and return a bearer token."""
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
    """Build standard bearer auth headers for API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def unique_user_identity() -> tuple[str, str, str]:
    """Generate unique credentials to avoid collisions across runs."""
    ts = int(time.time() * 1000)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"perf_{ts}_{suffix}"
    email = f"{username}@example.com"
    password = "PerfPass123!"
    return username, email, password


def random_status() -> str:
    """Pick a task status value supported by the API."""
    return random.choice(["pending", "in_progress", "completed"])


def random_task_payload() -> dict[str, Any]:
    """Build a valid task-create payload with small randomized variance."""
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
    """Build a valid task-update payload."""
    base = random_task_payload()

    # Keep updates lightweight: mutate a subset of mutable fields.
    candidates: list[dict[str, Any]] = [
        {"title": base["title"]},
        {"description": f"Updated at {datetime.now(timezone.utc).isoformat()}"},
        {"priority": base["priority"]},
        {"status": base["status"]},
        {"estimated_minutes": base["estimated_minutes"]},
    ]
    return random.choice(candidates)
