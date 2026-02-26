"""
End-to-end browser flows for the microservices task manager.

These tests drive a real browser (via Playwright) against the full
running stack -- gateway, auth-service, task-service, and the
Tasks-UI frontend.  Every request travels through the same HTTP path
a real user would follow, so failures here surface integration issues
that unit or contract tests cannot catch.

The suite is organised around user-visible workflows (authentication,
CRUD, multi-user isolation) and relies on the Page Object Model to
keep selectors and navigation out of test logic.

Key SDET Concepts Demonstrated:
- End-to-end testing with Playwright (browser automation)
- Page Object Model (POM) for maintainable UI tests
- Real HTTP through the API gateway (no mocks)
- Fixture-based test setup (pytest + Playwright fixtures)
- Multi-user browser isolation with separate browser contexts
- AAA pattern (Arrange / Act / Assert) in every test
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from playwright.sync_api import expect

from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.register_page import RegisterPage
from tests.e2e.pages.task_form_page import TaskFormPage
from tests.e2e.pages.task_list_page import TaskListPage

pytestmark = pytest.mark.e2e


def _register_and_login(base_url: str, page, credentials: dict[str, str]) -> None:
    """Register a new user and log them in via the UI.

    This helper encapsulates the two-step onboarding flow so that
    multi-user tests can spin up authenticated sessions concisely.

    Args:
        base_url: Root URL of the running gateway.
        page: Playwright Page instance to drive.
        credentials: Dict with ``username``, ``email``, and ``password``.
    """
    register_page = RegisterPage(page, base_url)
    login_page = LoginPage(page, base_url)

    register_page.navigate()
    register_page.register(
        username=credentials["username"],
        email=credentials["email"],
        password=credentials["password"],
    )
    login_page.login(
        username=credentials["username"],
        password=credentials["password"],
    )
    expect(page).to_have_url(re.compile(r".*/$"))


class TestAuthenticationFlow:
    """Tests for user authentication workflows (login, register, logout)."""

    def test_unauthenticated_user_redirected_to_login(self, page, live_server):
        """Test that visiting the root URL without a session redirects to /login."""
        # Arrange -- nothing to set up; start with a fresh browser page

        # Act
        page.goto(f"{live_server}/")
        page.wait_for_load_state("networkidle")

        # Assert
        expect(page).to_have_url(re.compile(r".*/login$"))

    def test_register_and_login_journey(
        self,
        register_page: RegisterPage,
        login_page: LoginPage,
        credential_factory: Callable[[str], dict[str, str]],
    ):
        """Test the full registration-then-login happy path."""
        # Arrange
        credentials = credential_factory("journey")

        # Act
        # ===== REGISTER =====
        register_page.navigate()
        register_page.register(
            username=credentials["username"],
            email=credentials["email"],
            password=credentials["password"],
        )
        register_page.assert_url_contains("/login")

        # ===== LOGIN =====
        login_page.login(
            username=credentials["username"],
            password=credentials["password"],
        )

        # Assert
        login_page.assert_url_contains("/")
        expect(login_page.get_by_test_id("page-title")).to_have_text("Tasks")

    def test_logout_clears_session(self, authenticated_user, page, live_server):
        """Test that logging out destroys the session and blocks re-entry."""
        # Arrange -- authenticated_user fixture already logged the user in

        # Act
        page.get_by_test_id("logout-button").click()
        page.wait_for_load_state("networkidle")

        # Assert -- user lands on /login and cannot sneak back in
        expect(page).to_have_url(re.compile(r".*/login$"))

        page.goto(f"{live_server}/")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(re.compile(r".*/login$"))


class TestTaskCreationFlow:
    """Tests for creating new tasks through the UI form."""

    @pytest.mark.smoke
    def test_create_task_with_all_fields(self, task_form_page, task_list_page):
        """Test creating a task with every field populated."""
        # Arrange
        task_data = {
            "title": "Complete Playwright Tutorial",
            "description": "Learn all about E2E testing with Playwright",
            "status": "pending",
            "priority": "high",
            "due_date": "2025-12-31T17:00",
        }

        # Act
        task_form_page.create_task(**task_data)

        # Assert
        task_form_page.assert_url_contains("/")
        task_form_page.assert_flash_success_visible()

        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert task_data["title"] in titles

    def test_create_task_with_minimal_fields(self, task_form_page, task_list_page):
        """Test creating a task with only the required title field."""
        # Arrange
        title = "Minimal Task"

        # Act
        task_form_page.fill_title(title)
        task_form_page.submit()

        # Assert
        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert title in titles

    def test_cancel_task_creation_returns_to_list(self, task_form_page):
        """Test that cancelling the form discards input and navigates back."""
        # Arrange
        task_form_page.fill_title("This should not be saved")

        # Act
        task_form_page.cancel()

        # Assert
        task_form_page.assert_url_contains("/")


class TestTaskViewFlow:
    """Tests for viewing task details from the task list."""

    def test_view_task_details_from_list(self, task_form_page, task_list_page, page):
        """Test that clicking a task in the list shows its full details."""
        # Arrange
        task_data = {
            "title": "Task to View",
            "description": "Detailed description for viewing",
            "priority": "high",
        }
        task_form_page.create_task(**task_data)

        # Act
        task_list_page.navigate()
        page.get_by_text(task_data["title"]).click()
        page.wait_for_load_state("networkidle")

        # Assert
        expect(page.get_by_test_id("task-title")).to_have_text(task_data["title"])
        expect(page.get_by_test_id("task-description")).to_contain_text(
            task_data["description"]
        )


class TestTaskEditFlow:
    """Tests for editing existing tasks through the UI."""

    def test_edit_task_updates_values(self, task_form_page, task_list_page, page):
        """Test that editing a task persists the new values."""
        # Arrange
        # ===== CREATE ORIGINAL TASK =====
        task_form_page.create_task(
            title="Original Title",
            description="Original description",
            priority="low",
        )

        # Act
        # ===== EDIT THE TASK =====
        task_list_page.navigate()
        page.locator("[data-testid^='edit-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        task_form_page.fill_title("Updated Title")
        task_form_page.fill_description("Updated description")
        task_form_page.select_priority("high")
        task_form_page.submit()

        # Assert
        # ===== VERIFY =====
        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert "Updated Title" in titles
        assert "Original Title" not in titles


class TestTaskDeletionFlow:
    """Tests for deleting tasks through the UI."""

    def test_delete_task_removes_from_list(self, task_form_page, task_list_page, page):
        """Test that deleting a task removes it from the task list."""
        # Arrange
        task_title = "Task to Delete"
        task_form_page.create_task(title=task_title)

        task_list_page.navigate()
        initial_count = task_list_page.get_task_count()

        # Act -- accept the browser confirmation dialog, then click delete
        page.on("dialog", lambda dialog: dialog.accept())
        page.locator("[data-testid^='delete-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Assert
        task_list_page.assert_flash_success_visible()
        titles = task_list_page.get_all_task_titles()
        assert task_title not in titles
        assert task_list_page.get_task_count() == initial_count - 1


class TestCompleteTaskLifecycle:
    """Tests for the full create-read-update-delete lifecycle of a task."""

    def test_full_task_lifecycle(self, task_form_page, task_list_page, page):
        """Test the complete CRUD lifecycle: create, view, edit, then delete."""
        # Arrange -- fixtures provide the authenticated browser session

        # Act & Assert -- each lifecycle phase validates before proceeding
        # ===== CREATE =====
        task_form_page.create_task(
            title="Lifecycle Test Task",
            description="Testing the complete lifecycle",
            status="pending",
            priority="medium",
        )

        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        assert "Lifecycle Test Task" in task_list_page.get_all_task_titles()

        # ===== VIEW =====
        page.get_by_text("Lifecycle Test Task").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_test_id("task-title")).to_have_text("Lifecycle Test Task")

        # ===== EDIT =====
        page.get_by_test_id("edit-button").click()
        page.wait_for_load_state("networkidle")
        task_form_page.fill_title("Updated Lifecycle Task")
        task_form_page.select_status("completed")
        task_form_page.submit()

        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        assert "Updated Lifecycle Task" in task_list_page.get_all_task_titles()

        # ===== DELETE =====
        page.on("dialog", lambda dialog: dialog.accept())
        page.locator("[data-testid^='delete-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # ===== VERIFY =====
        task_list_page.assert_flash_success_visible()
        assert "Updated Lifecycle Task" not in task_list_page.get_all_task_titles()


class TestTaskEstimatedMinutesFlow:
    """Tests for the estimated-minutes field on tasks."""

    def test_create_task_with_estimated_minutes(self, task_form_page, task_list_page, page):
        """Test that a task created with an estimate displays the badge."""
        # Arrange
        task_data = {
            "title": "Task with Estimate",
            "description": "This task has a time estimate",
            "priority": "high",
            "estimated_minutes": 45,
        }

        # Act
        task_form_page.create_task(**task_data)

        # Assert
        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        assert task_data["title"] in task_list_page.get_all_task_titles()

        estimate_badge = page.locator("[data-testid^='task-estimate-']").first
        expect(estimate_badge).to_contain_text("45 min")

    def test_edit_task_estimated_minutes(self, task_form_page, task_list_page, page):
        """Test that editing the estimate updates the displayed badge."""
        # Arrange
        # ===== CREATE TASK WITH INITIAL ESTIMATE =====
        task_form_page.create_task(title="Task to Update Estimate", estimated_minutes=30)

        # Act
        # ===== EDIT THE ESTIMATE =====
        task_list_page.navigate()
        page.locator("[data-testid^='edit-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        task_form_page.fill_estimated_minutes(60)
        task_form_page.submit()
        task_form_page.assert_flash_success_visible()

        # Assert
        # ===== VERIFY =====
        task_list_page.navigate()
        estimate_badge = page.locator("[data-testid^='task-estimate-']").first
        expect(estimate_badge).to_contain_text("60 min")


class TestTaskStatusFlow:
    """Tests for quick-status updates directly from the task list."""

    def test_quick_status_update_from_list(self, task_form_page, task_list_page, page):
        """Test changing a task's status via the inline dropdown."""
        # Arrange
        task_form_page.create_task(title="Quick Update Task", status="pending")
        task_list_page.navigate()

        # Act
        status_select = page.locator("[data-testid^='status-select-']").first
        status_select.select_option("completed")
        page.locator("[data-testid^='update-status-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Assert
        task_list_page.assert_flash_success_visible()
        status_badge = page.locator("[data-testid^='task-status-']").first
        expect(status_badge).to_contain_text("Completed")


class TestMultiUserE2E:
    """Tests for cross-user data isolation in the browser."""

    def test_user_1_task_is_hidden_from_user_2(
        self,
        browser,
        live_server,
        credential_factory: Callable[[str], dict[str, str]],
    ):
        """Test that one user's tasks are invisible to another user."""
        # Arrange
        private_title = "User1 Private Task"
        user1 = credential_factory("user1")
        user2 = credential_factory("user2")

        # Separate browser contexts give each user their own cookie jar
        context_1 = browser.new_context(viewport={"width": 1280, "height": 720})
        context_2 = browser.new_context(viewport={"width": 1280, "height": 720})
        # Act
        try:
            # ===== USER 1: REGISTER, LOGIN, CREATE TASK =====
            page_1 = context_1.new_page()
            _register_and_login(live_server, page_1, user1)

            user1_form = TaskFormPage(page_1, live_server)
            user1_form.navigate()
            user1_form.create_task(title=private_title)
            expect(page_1.get_by_text(private_title)).to_be_visible()

            page_1.get_by_test_id("logout-button").click()
            page_1.wait_for_load_state("networkidle")

            # ===== USER 2: REGISTER, LOGIN, VERIFY ISOLATION =====
            page_2 = context_2.new_page()
            _register_and_login(live_server, page_2, user2)

            user2_list = TaskListPage(page_2, live_server)
            user2_list.navigate()

            # Assert -- user 2 must NOT see user 1's task
            assert private_title not in user2_list.get_all_task_titles()
        finally:
            context_1.close()
            context_2.close()
