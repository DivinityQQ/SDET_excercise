"""Playwright fixtures for microservices E2E tests."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Callable, Generator

import pytest
import requests
from playwright.sync_api import Browser, BrowserContext, Page

from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.register_page import RegisterPage
from tests.e2e.pages.task_form_page import TaskFormPage
from tests.e2e.pages.task_list_page import TaskListPage


def _wait_for_healthy(url: str, timeout: int = 60, interval: int = 1) -> None:
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


def _wait_for_auth_healthy(url: str, timeout: int = 60, interval: int = 1) -> None:
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


@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique id for current E2E run to avoid data collisions."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def live_server(test_run_id: str) -> Generator[str, None, None]:
    """
    Return a live gateway URL for E2E tests.

    If TEST_BASE_URL is set, use that stack.
    Otherwise start docker compose test stack and tear it down afterwards.
    """
    provided_base_url = os.getenv("TEST_BASE_URL")
    if provided_base_url:
        _wait_for_healthy(provided_base_url)
        _wait_for_auth_healthy(provided_base_url)
        yield provided_base_url
        return

    project_name = os.getenv("E2E_COMPOSE_PROJECT", f"taskapp-e2e-{test_run_id}")
    compose_file = os.getenv("E2E_COMPOSE_FILE", "docker-compose.test.yml")
    base_url = "http://localhost:5000"

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
        pytest.skip("docker is not installed; set TEST_BASE_URL to run E2E tests")
    except subprocess.CalledProcessError as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise RuntimeError(
            f"Failed to start docker compose stack.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        ) from exc

    try:
        _wait_for_healthy(base_url)
        _wait_for_auth_healthy(base_url)
        yield base_url
    finally:
        subprocess.run(compose_down_cmd, check=False)


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def context(
    browser: Browser, browser_context_args: dict
) -> Generator[BrowserContext, None, None]:
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture
def credential_factory(test_run_id: str) -> Callable[[str], dict[str, str]]:
    """Factory for unique E2E user credentials."""

    def _make(prefix: str = "user") -> dict[str, str]:
        suffix = uuid.uuid4().hex[:6]
        username = f"e2e_{test_run_id}_{prefix}_{suffix}"
        return {
            "username": username,
            "email": f"{username}@test.com",
            "password": "E2EPass123!",
        }

    return _make


@pytest.fixture
def login_page(page: Page, live_server: str) -> LoginPage:
    return LoginPage(page, live_server)


@pytest.fixture
def register_page(page: Page, live_server: str) -> RegisterPage:
    return RegisterPage(page, live_server)


@pytest.fixture
def authenticated_user(
    credential_factory: Callable[[str], dict[str, str]],
    register_page: RegisterPage,
    login_page: LoginPage,
) -> dict[str, str]:
    """Register and login a unique user in current browser context."""
    credentials = credential_factory("auth")
    register_page.navigate()
    register_page.register(
        username=credentials["username"],
        email=credentials["email"],
        password=credentials["password"],
    )
    login_page.assert_url_contains("/login")

    login_page.login(
        username=credentials["username"],
        password=credentials["password"],
    )
    login_page.assert_url_contains("/")
    return credentials


@pytest.fixture
def task_list_page(page: Page, live_server: str, authenticated_user) -> TaskListPage:
    return TaskListPage(page, live_server)


@pytest.fixture
def task_form_page(page: Page, live_server: str, authenticated_user) -> TaskFormPage:
    task_form = TaskFormPage(page, live_server)
    task_form.navigate()
    return task_form


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot on UI test failure."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        if page:
            screenshot_dir = "test-results/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            test_name = item.name.replace("/", "_").replace("::", "_")
            screenshot_path = f"{screenshot_dir}/{test_name}.png"
            try:
                page.screenshot(path=screenshot_path)
                print(f"\nScreenshot saved: {screenshot_path}")
            except Exception as exc:  # pragma: no cover - best effort logging
                print(f"\nFailed to capture screenshot: {exc}")

