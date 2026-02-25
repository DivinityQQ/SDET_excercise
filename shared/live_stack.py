"""Shared live-stack helpers for smoke and E2E test suites."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Generator

import pytest
import requests


def is_stack_ready(url: str, timeout: int = 2) -> bool:
    """Return True when gateway and auth health endpoints both respond with 200."""
    try:
        gateway_response = requests.get(f"{url}/api/health", timeout=timeout)
        auth_response = requests.get(f"{url}/api/auth/health", timeout=timeout)
    except requests.RequestException:
        return False
    return gateway_response.status_code == 200 and auth_response.status_code == 200


def wait_for_gateway_healthy(url: str, timeout: int = 60, interval: int = 1) -> None:
    """Poll gateway health endpoint until ready or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{url}/api/health", timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(interval)
    raise RuntimeError(f"Gateway at {url} not healthy after {timeout}s")


def wait_for_auth_healthy(url: str, timeout: int = 60, interval: int = 1) -> None:
    """Poll auth health endpoint exposed via gateway."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{url}/api/auth/health", timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(interval)
    raise RuntimeError(f"Auth service via gateway at {url} not healthy after {timeout}s")


def live_stack_url(
    *,
    base_url_env: str,
    compose_project_env: str,
    compose_file_env: str,
    compose_project_default: str,
    suite_name: str,
    compose_file_default: str = "docker-compose.test.yml",
    base_url_default: str = "http://localhost:5000",
) -> Generator[str, None, None]:
    """
    Yield a healthy gateway base URL, reusing or starting a compose stack when needed.

    Priority:
    1. Use explicit base URL from `base_url_env` (and wait for health).
    2. Reuse an already-running local stack at `base_url_default`.
    3. Start compose stack, wait for health, then tear it down on exit.
    """
    provided_base_url = os.getenv(base_url_env)
    if provided_base_url:
        wait_for_gateway_healthy(provided_base_url)
        wait_for_auth_healthy(provided_base_url)
        yield provided_base_url
        return

    base_url = base_url_default
    if is_stack_ready(base_url):
        yield base_url
        return

    project_name = os.getenv(compose_project_env, compose_project_default)
    compose_file = os.getenv(compose_file_env, compose_file_default)

    compose_up_cmd = [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        compose_file,
        "up",
        "-d",
        "--build",
    ]
    compose_down_cmd = [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        compose_file,
        "down",
        "-v",
        "--remove-orphans",
    ]

    try:
        subprocess.run(
            compose_up_cmd,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        pytest.skip(
            f"docker is not installed; set {base_url_env} to run {suite_name} tests"
        )
    except subprocess.CalledProcessError as exc:
        # Best-effort cleanup in case compose created partial resources
        # before failing (containers, networks, volumes).
        subprocess.run(
            compose_down_cmd,
            check=False,
            text=True,
            capture_output=True,
        )
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise RuntimeError(
            f"Failed to start docker compose stack.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        ) from exc

    try:
        wait_for_gateway_healthy(base_url)
        wait_for_auth_healthy(base_url)
        yield base_url
    finally:
        subprocess.run(compose_down_cmd, check=False)
