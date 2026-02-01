"""
Task List Page Object.

This page object encapsulates all interactions with the task list page,
including filtering, viewing tasks, and quick actions.

Key Concepts Demonstrated:
- Page-specific locators
- Complex interactions (filtering, quick status update)
- Data extraction from page
- Waiting for dynamic content
"""

from playwright.sync_api import Page, Locator, expect
from tests.e2e.pages.base_page import BasePage


class TaskListPage(BasePage):
    """
    Page object for the task list page (home page).

    Provides methods for:
    - Viewing and filtering tasks
    - Quick status updates
    - Navigation to task details/edit
    - Task deletion
    """

    URL_PATH = "/"

    def __init__(self, page: Page, base_url: str):
        """
        Initialize TaskListPage.

        Args:
            page: Playwright page instance.
            base_url: Base URL of the application.
        """
        super().__init__(page, base_url)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def navigate(self) -> "TaskListPage":
        """
        Navigate to the task list page.

        Returns:
            Self for method chaining.
        """
        self.navigate_to(self.URL_PATH)
        self.wait_for_page_load()
        return self

    # -------------------------------------------------------------------------
    # Page Locators
    # -------------------------------------------------------------------------

    @property
    def page_title(self) -> Locator:
        """Locator for the page title."""
        return self.get_by_test_id("page-title")

    @property
    def task_list(self) -> Locator:
        """Locator for the task list container."""
        return self.get_by_test_id("task-list")

    @property
    def task_count(self) -> Locator:
        """Locator for the task count display."""
        return self.get_by_test_id("task-count")

    @property
    def empty_state(self) -> Locator:
        """Locator for the empty state message."""
        return self.get_by_test_id("empty-state")

    @property
    def status_filter(self) -> Locator:
        """Locator for the status filter dropdown."""
        return self.get_by_test_id("status-filter")

    @property
    def priority_filter(self) -> Locator:
        """Locator for the priority filter dropdown."""
        return self.get_by_test_id("priority-filter")

    @property
    def filter_button(self) -> Locator:
        """Locator for the filter submit button."""
        return self.get_by_test_id("filter-button")

    @property
    def clear_filters(self) -> Locator:
        """Locator for the clear filters link."""
        return self.get_by_test_id("clear-filters")

    # -------------------------------------------------------------------------
    # Task Item Locators (by ID)
    # -------------------------------------------------------------------------

    def get_task_item(self, task_id: int) -> Locator:
        """
        Get locator for a specific task item.

        Args:
            task_id: ID of the task.

        Returns:
            Locator for the task item.
        """
        return self.get_by_test_id(f"task-item-{task_id}")

    def get_task_title(self, task_id: int) -> Locator:
        """Get locator for a task's title link."""
        return self.get_by_test_id(f"task-title-{task_id}")

    def get_task_status(self, task_id: int) -> Locator:
        """Get locator for a task's status badge."""
        return self.get_by_test_id(f"task-status-{task_id}")

    def get_task_priority(self, task_id: int) -> Locator:
        """Get locator for a task's priority badge."""
        return self.get_by_test_id(f"task-priority-{task_id}")

    def get_edit_button(self, task_id: int) -> Locator:
        """Get locator for a task's edit button."""
        return self.get_by_test_id(f"edit-btn-{task_id}")

    def get_delete_button(self, task_id: int) -> Locator:
        """Get locator for a task's delete button."""
        return self.get_by_test_id(f"delete-btn-{task_id}")

    def get_status_select(self, task_id: int) -> Locator:
        """Get locator for a task's quick status select."""
        return self.get_by_test_id(f"status-select-{task_id}")

    def get_update_status_button(self, task_id: int) -> Locator:
        """Get locator for a task's update status button."""
        return self.get_by_test_id(f"update-status-btn-{task_id}")

    def get_task_estimate(self, task_id: int) -> Locator:
        """Get locator for a task's estimated duration badge."""
        return self.get_by_test_id(f"task-estimate-{task_id}")

    # -------------------------------------------------------------------------
    # Page Actions
    # -------------------------------------------------------------------------

    def filter_by_status(self, status: str) -> "TaskListPage":
        """
        Filter tasks by status.

        Args:
            status: Status value to filter by (or empty for all).

        Returns:
            Self for method chaining.
        """
        self.status_filter.select_option(status)
        self.filter_button.click()
        self.wait_for_page_load()
        return self

    def filter_by_priority(self, priority: str) -> "TaskListPage":
        """
        Filter tasks by priority.

        Args:
            priority: Priority value to filter by (or empty for all).

        Returns:
            Self for method chaining.
        """
        self.priority_filter.select_option(priority)
        self.filter_button.click()
        self.wait_for_page_load()
        return self

    def clear_all_filters(self) -> "TaskListPage":
        """
        Clear all applied filters.

        Returns:
            Self for method chaining.
        """
        self.clear_filters.click()
        self.wait_for_page_load()
        return self

    def click_task(self, task_id: int) -> None:
        """
        Click on a task to view its details.

        Args:
            task_id: ID of the task to click.
        """
        self.get_task_title(task_id).click()
        self.wait_for_page_load()

    def click_edit(self, task_id: int) -> None:
        """
        Click the edit button for a task.

        Args:
            task_id: ID of the task to edit.
        """
        self.get_edit_button(task_id).click()
        self.wait_for_page_load()

    def quick_update_status(self, task_id: int, new_status: str) -> "TaskListPage":
        """
        Quickly update a task's status from the list view.

        Args:
            task_id: ID of the task to update.
            new_status: New status value.

        Returns:
            Self for method chaining.
        """
        self.get_status_select(task_id).select_option(new_status)
        self.get_update_status_button(task_id).click()
        self.wait_for_page_load()
        return self

    def delete_task(self, task_id: int) -> "TaskListPage":
        """
        Delete a task from the list.

        Note: This will trigger a confirmation dialog.

        Args:
            task_id: ID of the task to delete.

        Returns:
            Self for method chaining.
        """
        # Handle the confirmation dialog
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.get_delete_button(task_id).click()
        self.wait_for_page_load()
        return self

    # -------------------------------------------------------------------------
    # Data Extraction
    # -------------------------------------------------------------------------

    def get_task_count(self) -> int:
        """
        Get the number of tasks displayed.

        Returns:
            Number of tasks shown on the page.
        """
        text = self.task_count.text_content()
        # Extract number from "Showing X task(s)"
        import re
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0

    def get_all_task_titles(self) -> list[str]:
        """
        Get titles of all visible tasks.

        Returns:
            List of task titles (whitespace stripped).
        """
        # Find all task title elements
        title_elements = self.page.locator("[data-testid^='task-title-']").all()
        return [elem.text_content().strip() for elem in title_elements]

    # -------------------------------------------------------------------------
    # Assertions
    # -------------------------------------------------------------------------

    def assert_task_visible(self, task_id: int) -> None:
        """Assert that a task is visible on the page."""
        expect(self.get_task_item(task_id)).to_be_visible()

    def assert_task_not_visible(self, task_id: int) -> None:
        """Assert that a task is not visible on the page."""
        expect(self.get_task_item(task_id)).not_to_be_visible()

    def assert_task_has_status(self, task_id: int, expected_status: str) -> None:
        """Assert that a task has the expected status."""
        status_text = self.get_task_status(task_id).text_content().lower()
        assert expected_status.replace("_", " ") in status_text

    def assert_task_has_priority(self, task_id: int, expected_priority: str) -> None:
        """Assert that a task has the expected priority."""
        priority_text = self.get_task_priority(task_id).text_content().lower()
        assert expected_priority in priority_text

    def assert_empty_state_visible(self) -> None:
        """Assert that the empty state is displayed."""
        expect(self.empty_state).to_be_visible()

    def assert_task_count_equals(self, expected: int) -> None:
        """Assert that the displayed task count matches expected."""
        actual = self.get_task_count()
        assert actual == expected, f"Expected {expected} tasks, but found {actual}"

    def assert_task_has_estimate(self, task_id: int, expected_minutes: int) -> None:
        """Assert that a task has the expected estimated duration."""
        estimate_text = self.get_task_estimate(task_id).text_content()
        assert f"{expected_minutes} min" in estimate_text
