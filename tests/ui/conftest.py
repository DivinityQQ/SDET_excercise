"""
Playwright fixtures for UI tests.

This module provides fixtures specific to browser-based UI testing
using Playwright. It integrates with the Flask test server and
provides page objects for testing.

Key Concepts Demonstrated:
- Live server fixture for Playwright
- Browser context management
- Screenshot capture on failure
- Page object initialization
"""

import os
import pytest
import threading
from typing import Generator
from playwright.sync_api import Page, Browser, BrowserContext

# Set testing environment
os.environ["FLASK_ENV"] = "testing"

from app import create_app, db
from tests.ui.pages.task_list_page import TaskListPage
from tests.ui.pages.task_form_page import TaskFormPage


# -----------------------------------------------------------------------------
# Server Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create Flask application for UI tests."""
    application = create_app("testing")
    return application


@pytest.fixture(scope="session")
def live_server(app):
    """
    Start a live Flask server for Playwright tests.

    This fixture starts the Flask development server in a background
    thread, allowing Playwright to make real HTTP requests.

    Yields:
        str: Base URL of the running server.
    """
    # Configure server
    host = "127.0.0.1"
    port = 5001  # Use different port to avoid conflicts

    # Ensure database tables exist before starting server
    with app.app_context():
        db.create_all()

    # Create and start server thread
    server_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, use_reloader=False, threaded=True)
    )
    server_thread.daemon = True
    server_thread.start()

    # Give server time to start
    import time
    time.sleep(1)

    base_url = f"http://{host}:{port}"

    yield base_url

    # Server will stop when test session ends (daemon thread)


@pytest.fixture(scope="function")
def clean_db(app):
    """
    Ensure clean database state for each UI test.

    This fixture clears all task data before each test to ensure
    test isolation, while keeping the schema intact.
    """
    with app.app_context():
        # Clear all tasks (not drop/create to avoid schema issues across threads)
        from app.models import Task
        db.session.query(Task).delete()
        db.session.commit()
        yield db
        # Clean up after test
        db.session.query(Task).delete()
        db.session.commit()


# -----------------------------------------------------------------------------
# Browser Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args():
    """
    Configure browser context options.

    Returns:
        dict: Browser context configuration.
    """
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def context(browser: Browser, browser_context_args: dict) -> Generator[BrowserContext, None, None]:
    """
    Create a fresh browser context for each test.

    A new context ensures test isolation - cookies, localStorage,
    and session data are not shared between tests.

    Args:
        browser: Playwright browser instance.
        browser_context_args: Context configuration.

    Yields:
        BrowserContext: Fresh browser context.
    """
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """
    Create a new page (tab) for each test.

    Args:
        context: Browser context fixture.

    Yields:
        Page: Playwright page object.
    """
    page = context.new_page()
    yield page
    page.close()


# -----------------------------------------------------------------------------
# Page Object Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def task_list_page(page: Page, live_server: str, clean_db) -> TaskListPage:
    """
    Initialize TaskListPage (without navigating).

    The page object is ready to use - call .navigate() when needed.
    Not auto-navigating allows tests to use multiple page objects
    without conflict.

    Args:
        page: Playwright page fixture.
        live_server: Base URL of live server.
        clean_db: Ensures clean database.

    Returns:
        TaskListPage: Initialized page object (not yet navigated).
    """
    return TaskListPage(page, live_server)


@pytest.fixture
def task_form_page(page: Page, live_server: str, clean_db) -> TaskFormPage:
    """
    Initialize TaskFormPage and navigate to new task form.

    Unlike task_list_page, this auto-navigates because tests
    typically start by creating a task.

    Args:
        page: Playwright page fixture.
        live_server: Base URL of live server.
        clean_db: Ensures clean database.

    Returns:
        TaskFormPage: Initialized page object on the form page.
    """
    task_form = TaskFormPage(page, live_server)
    task_form.navigate()
    return task_form


# -----------------------------------------------------------------------------
# Screenshot on Failure
# -----------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Capture screenshot on test failure.

    This pytest hook captures a screenshot when a UI test fails,
    which is invaluable for debugging test failures.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # Check if this is a UI test with a page fixture
        page = item.funcargs.get("page")
        if page:
            # Create screenshots directory if it doesn't exist
            screenshot_dir = "test-results/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)

            # Generate screenshot filename
            test_name = item.name.replace("/", "_").replace("::", "_")
            screenshot_path = f"{screenshot_dir}/{test_name}.png"

            # Capture screenshot
            try:
                page.screenshot(path=screenshot_path)
                print(f"\nScreenshot saved: {screenshot_path}")
            except Exception as e:
                print(f"\nFailed to capture screenshot: {e}")
