"""
Task Form Page Object.

This page object encapsulates all interactions with the task creation
and editing forms.

Key Concepts Demonstrated:
- Form field interactions
- Form submission
- Input validation testing
- Reusable form methods for create/edit
"""

from playwright.sync_api import Page, Locator, expect
from tests.ui.pages.base_page import BasePage


class TaskFormPage(BasePage):
    """
    Page object for the task create/edit form.

    Provides methods for:
    - Filling form fields
    - Submitting the form
    - Validating form state
    - Handling form errors
    """

    NEW_TASK_URL = "/tasks/new"

    def __init__(self, page: Page, base_url: str):
        """
        Initialize TaskFormPage.

        Args:
            page: Playwright page instance.
            base_url: Base URL of the application.
        """
        super().__init__(page, base_url)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def navigate(self) -> "TaskFormPage":
        """
        Navigate to the new task form.

        Returns:
            Self for method chaining.
        """
        self.navigate_to(self.NEW_TASK_URL)
        self.wait_for_page_load()
        return self

    def navigate_to_edit(self, task_id: int) -> "TaskFormPage":
        """
        Navigate to the edit form for a specific task.

        Args:
            task_id: ID of the task to edit.

        Returns:
            Self for method chaining.
        """
        self.navigate_to(f"/tasks/{task_id}/edit")
        self.wait_for_page_load()
        return self

    # -------------------------------------------------------------------------
    # Form Locators
    # -------------------------------------------------------------------------

    @property
    def form_title(self) -> Locator:
        """Locator for the form title (Create/Edit)."""
        return self.get_by_test_id("form-title")

    @property
    def title_input(self) -> Locator:
        """Locator for the title input field."""
        return self.get_by_test_id("title-input")

    @property
    def description_input(self) -> Locator:
        """Locator for the description textarea."""
        return self.get_by_test_id("description-input")

    @property
    def status_select(self) -> Locator:
        """Locator for the status dropdown."""
        return self.get_by_test_id("status-input")

    @property
    def priority_select(self) -> Locator:
        """Locator for the priority dropdown."""
        return self.get_by_test_id("priority-input")

    @property
    def due_date_input(self) -> Locator:
        """Locator for the due date input."""
        return self.get_by_test_id("due-date-input")

    @property
    def submit_button(self) -> Locator:
        """Locator for the submit button."""
        return self.get_by_test_id("submit-button")

    @property
    def cancel_button(self) -> Locator:
        """Locator for the cancel button."""
        return self.get_by_test_id("cancel-button")

    # -------------------------------------------------------------------------
    # Form Actions
    # -------------------------------------------------------------------------

    def fill_title(self, title: str) -> "TaskFormPage":
        """
        Fill the title field.

        Args:
            title: Task title to enter.

        Returns:
            Self for method chaining.
        """
        self.title_input.fill(title)
        return self

    def fill_description(self, description: str) -> "TaskFormPage":
        """
        Fill the description field.

        Args:
            description: Task description to enter.

        Returns:
            Self for method chaining.
        """
        self.description_input.fill(description)
        return self

    def select_status(self, status: str) -> "TaskFormPage":
        """
        Select a status from the dropdown.

        Args:
            status: Status value to select.

        Returns:
            Self for method chaining.
        """
        self.status_select.select_option(status)
        return self

    def select_priority(self, priority: str) -> "TaskFormPage":
        """
        Select a priority from the dropdown.

        Args:
            priority: Priority value to select.

        Returns:
            Self for method chaining.
        """
        self.priority_select.select_option(priority)
        return self

    def fill_due_date(self, date_string: str) -> "TaskFormPage":
        """
        Fill the due date field.

        Args:
            date_string: Date in format YYYY-MM-DDTHH:MM.

        Returns:
            Self for method chaining.
        """
        self.due_date_input.fill(date_string)
        return self

    def clear_due_date(self) -> "TaskFormPage":
        """
        Clear the due date field.

        Returns:
            Self for method chaining.
        """
        self.due_date_input.clear()
        return self

    def submit(self) -> None:
        """Submit the form."""
        self.submit_button.click()
        self.wait_for_page_load()

    def cancel(self) -> None:
        """Click cancel to return to task list."""
        self.cancel_button.click()
        self.wait_for_page_load()

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    def fill_form(
        self,
        title: str,
        description: str = "",
        status: str = "pending",
        priority: str = "medium",
        due_date: str = ""
    ) -> "TaskFormPage":
        """
        Fill all form fields at once.

        Args:
            title: Task title.
            description: Task description.
            status: Task status.
            priority: Task priority.
            due_date: Due date string.

        Returns:
            Self for method chaining.
        """
        self.fill_title(title)

        if description:
            self.fill_description(description)

        self.select_status(status)
        self.select_priority(priority)

        if due_date:
            self.fill_due_date(due_date)

        return self

    def create_task(
        self,
        title: str,
        description: str = "",
        status: str = "pending",
        priority: str = "medium",
        due_date: str = ""
    ) -> None:
        """
        Fill form and submit to create a new task.

        Args:
            title: Task title.
            description: Task description.
            status: Task status.
            priority: Task priority.
            due_date: Due date string.
        """
        self.fill_form(title, description, status, priority, due_date)
        self.submit()

    # -------------------------------------------------------------------------
    # Data Extraction
    # -------------------------------------------------------------------------

    def get_title_value(self) -> str:
        """Get current value of title field."""
        return self.title_input.input_value()

    def get_description_value(self) -> str:
        """Get current value of description field."""
        return self.description_input.input_value()

    def get_status_value(self) -> str:
        """Get current selected status."""
        return self.status_select.input_value()

    def get_priority_value(self) -> str:
        """Get current selected priority."""
        return self.priority_select.input_value()

    def get_due_date_value(self) -> str:
        """Get current value of due date field."""
        return self.due_date_input.input_value()

    # -------------------------------------------------------------------------
    # Assertions
    # -------------------------------------------------------------------------

    def assert_form_title(self, expected: str) -> None:
        """Assert the form title matches expected."""
        expect(self.form_title).to_have_text(expected)

    def assert_title_required(self) -> None:
        """Assert that title field is marked as required."""
        # HTML5 required attribute
        expect(self.title_input).to_have_attribute("required", "")

    def assert_title_has_value(self, expected: str) -> None:
        """Assert title field has expected value."""
        expect(self.title_input).to_have_value(expected)

    def assert_status_selected(self, expected: str) -> None:
        """Assert expected status is selected."""
        expect(self.status_select).to_have_value(expected)

    def assert_priority_selected(self, expected: str) -> None:
        """Assert expected priority is selected."""
        expect(self.priority_select).to_have_value(expected)

    def assert_form_is_empty(self) -> None:
        """Assert all form fields are empty (for new task form)."""
        expect(self.title_input).to_have_value("")
        expect(self.description_input).to_have_value("")

    def assert_on_create_form(self) -> None:
        """Assert we are on the create task form."""
        self.assert_form_title("Create New Task")
        self.assert_url_contains("/tasks/new")

    def assert_on_edit_form(self) -> None:
        """Assert we are on the edit task form."""
        self.assert_form_title("Edit Task")
        self.assert_url_contains("/edit")
