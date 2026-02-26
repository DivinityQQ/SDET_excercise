"""
Playwright fixtures for microservices E2E tests.

Provides session-, function-, and helper-scoped pytest fixtures for
browser-based end-to-end tests.  The ``live_server`` fixture manages stack
lifecycle via :func:`shared.live_stack.live_stack_url`, and the page fixtures
wrap Playwright's ``Browser`` and ``BrowserContext`` for per-test isolation.

Key SDET Concepts Demonstrated:
- Page Object fixtures for clean separation between test logic and UI interactions
- Session-scoped live-server management shared across the full E2E suite
- Per-function browser context and page to prevent session state leaking between tests
- Credential factories for collision-free unique test data across parallel runs
- Automatic screenshot capture on failure for post-mortem debugging
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page
    from tests.e2e.pages.login_page import LoginPage
    from tests.e2e.pages.register_page import RegisterPage
    from tests.e2e.pages.task_form_page import TaskFormPage
    from tests.e2e.pages.task_list_page import TaskListPage
else:  # pragma: no cover - runtime fallback when Playwright is not installed
    Browser = BrowserContext = Page = Any

from shared.live_stack import live_stack_url


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
    yield from live_stack_url(
        base_url_env="TEST_BASE_URL",
        compose_project_env="E2E_COMPOSE_PROJECT",
        compose_file_env="E2E_COMPOSE_FILE",
        compose_project_default=f"taskapp-e2e-{test_run_id}",
        suite_name="E2E",
    )


@pytest.fixture(scope="session")
def browser_context_args():
    """Default Playwright browser-context options for E2E tests."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def context(
    browser: Browser, browser_context_args: dict
) -> Generator[BrowserContext, None, None]:
    """Fresh browser context for each test function."""
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Fresh browser page within the function-scoped context."""
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
    """LoginPage instance bound to the current page and live server."""
    from tests.e2e.pages.login_page import LoginPage

    return LoginPage(page, live_server)


@pytest.fixture
def register_page(page: Page, live_server: str) -> RegisterPage:
    """RegisterPage instance bound to the current page and live server."""
    from tests.e2e.pages.register_page import RegisterPage

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
    """Authenticated TaskListPage instance for the current test."""
    from tests.e2e.pages.task_list_page import TaskListPage

    return TaskListPage(page, live_server)


@pytest.fixture
def task_form_page(page: Page, live_server: str, authenticated_user) -> TaskFormPage:
    """Authenticated TaskFormPage pre-navigated to the new-task form."""
    from tests.e2e.pages.task_form_page import TaskFormPage

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
