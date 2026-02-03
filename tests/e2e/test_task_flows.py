"""
End-to-End User Flow Tests using Playwright.

This module tests complete user journeys through the application,
simulating real user behavior with the browser.

Key SDET Concepts Demonstrated:
- E2E testing with real browser
- User flow testing (create → view → edit → delete)
- Page Object Model usage
- Test data management in UI tests
"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


class TestTaskCreationFlow:
    """Tests for the task creation user flow."""

    @pytest.mark.smoke
    def test_create_task_with_all_fields(self, task_form_page, task_list_page):
        """
        Test creating a task with all fields filled.

        User Flow:
        1. Navigate to new task form
        2. Fill all fields
        3. Submit form
        4. Verify redirect to task list
        5. Verify task appears in list
        """
        # Arrange
        task_data = {
            "title": "Complete Playwright Tutorial",
            "description": "Learn all about E2E testing with Playwright",
            "status": "pending",
            "priority": "high",
            "due_date": "2025-12-31T17:00"
        }

        # Act
        task_form_page.create_task(**task_data)

        # Assert
        task_form_page.assert_url_contains("/")
        task_form_page.assert_flash_success_visible()

        # Verify task appears in list
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert task_data["title"] in titles

    def test_create_task_with_minimal_fields(self, task_form_page, task_list_page):
        """
        Test creating a task with only required fields.

        User Flow:
        1. Navigate to new task form
        2. Fill only title
        3. Submit form
        4. Verify task is created with defaults
        """
        # Arrange
        title = "Minimal Task"

        # Act
        task_form_page.fill_title(title)
        task_form_page.submit()

        # Assert
        task_form_page.assert_flash_success_visible()

        # Verify task appears with default values
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert title in titles

    def test_cancel_task_creation_returns_to_list(self, task_form_page):
        """
        Test that canceling task creation returns to task list.

        User Flow:
        1. Navigate to new task form
        2. Fill some fields
        3. Click cancel
        4. Verify return to task list without saving
        """
        # Arrange
        task_form_page.fill_title("This should not be saved")

        # Act
        task_form_page.cancel()

        # Assert
        task_form_page.assert_url_contains("/")


class TestTaskViewFlow:
    """Tests for viewing task details."""

    def test_view_task_details_from_list(self, task_form_page, task_list_page, page):
        """
        Test clicking a task in the list shows details.

        User Flow:
        1. Create a task
        2. Click on task title in list
        3. Verify task detail page shows correct info
        """
        # Arrange - Create a task first
        task_data = {
            "title": "Task to View",
            "description": "Detailed description for viewing",
            "priority": "high"
        }
        task_form_page.create_task(**task_data)

        # Navigate to list and find the task
        task_list_page.navigate()

        # Act - Click on the task (find by title text)
        page.get_by_text(task_data["title"]).click()
        page.wait_for_load_state("networkidle")

        # Assert - Verify we're on detail page with correct content
        expect(page.get_by_test_id("task-title")).to_have_text(task_data["title"])
        expect(page.get_by_test_id("task-description")).to_contain_text(task_data["description"])


class TestTaskEditFlow:
    """Tests for editing tasks."""

    def test_edit_task_updates_values(self, task_form_page, task_list_page, page):
        """
        Test editing a task updates its values.

        User Flow:
        1. Create a task
        2. Navigate to edit form
        3. Change values
        4. Submit
        5. Verify changes are saved
        """
        # Arrange - Create initial task
        task_form_page.create_task(
            title="Original Title",
            description="Original description",
            priority="low"
        )

        # Get task ID from the list
        task_list_page.navigate()

        # Click edit on the first task
        page.locator("[data-testid^='edit-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Act - Update the task
        task_form_page.fill_title("Updated Title")
        task_form_page.fill_description("Updated description")
        task_form_page.select_priority("high")
        task_form_page.submit()

        # Assert
        task_form_page.assert_flash_success_visible()

        # Verify changes in list
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert "Updated Title" in titles
        assert "Original Title" not in titles


class TestTaskDeletionFlow:
    """Tests for deleting tasks."""

    def test_delete_task_removes_from_list(self, task_form_page, task_list_page, page):
        """
        Test deleting a task removes it from the list.

        User Flow:
        1. Create a task
        2. Delete it from the list
        3. Verify it no longer appears
        """
        # Arrange - Create a task to delete
        task_title = "Task to Delete"
        task_form_page.create_task(title=task_title)

        # Navigate to list
        task_list_page.navigate()
        initial_count = task_list_page.get_task_count()

        # Accept the confirmation dialog
        page.on("dialog", lambda dialog: dialog.accept())

        # Act - Click delete
        page.locator("[data-testid^='delete-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Assert
        task_list_page.assert_flash_success_visible()

        # Verify task is removed
        titles = task_list_page.get_all_task_titles()
        assert task_title not in titles
        assert task_list_page.get_task_count() == initial_count - 1


class TestCompleteTaskLifecycle:
    """Tests for complete task lifecycle (CRUD)."""

    @pytest.mark.slow
    def test_full_task_lifecycle(self, task_form_page, task_list_page, page):
        """
        Test complete task lifecycle: Create → Read → Update → Delete.

        This is a comprehensive test that verifies the entire
        user journey for task management.
        """
        # ===== CREATE =====
        task_form_page.create_task(
            title="Lifecycle Test Task",
            description="Testing the complete lifecycle",
            status="pending",
            priority="medium"
        )

        # Verify creation
        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        assert "Lifecycle Test Task" in task_list_page.get_all_task_titles()

        # ===== READ =====
        # View task details
        page.get_by_text("Lifecycle Test Task").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_test_id("task-title")).to_have_text("Lifecycle Test Task")

        # ===== UPDATE =====
        # Navigate to edit
        page.get_by_test_id("edit-button").click()
        page.wait_for_load_state("networkidle")

        # Update values
        task_form_page.fill_title("Updated Lifecycle Task")
        task_form_page.select_status("completed")
        task_form_page.submit()

        # Verify update
        task_form_page.assert_flash_success_visible()
        task_list_page.navigate()
        assert "Updated Lifecycle Task" in task_list_page.get_all_task_titles()

        # ===== DELETE =====
        # Handle confirmation dialog
        page.on("dialog", lambda dialog: dialog.accept())

        # Delete the task
        page.locator("[data-testid^='delete-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Verify deletion
        task_list_page.assert_flash_success_visible()
        assert "Updated Lifecycle Task" not in task_list_page.get_all_task_titles()


class TestTaskEstimatedMinutesFlow:
    """Tests for task estimated duration feature."""

    def test_create_task_with_estimated_minutes(self, task_form_page, task_list_page, page):
        """
        Test creating a task with estimated duration.

        User Flow:
        1. Navigate to new task form
        2. Fill form including estimated minutes
        3. Submit form
        4. Verify estimated duration shows in task list
        """
        # Arrange
        task_data = {
            "title": "Task with Estimate",
            "description": "This task has a time estimate",
            "priority": "high",
            "estimated_minutes": 45
        }

        # Act
        task_form_page.create_task(**task_data)

        # Assert
        task_form_page.assert_flash_success_visible()

        # Verify task appears in list with estimate
        task_list_page.navigate()
        titles = task_list_page.get_all_task_titles()
        assert task_data["title"] in titles

        # Verify estimate is displayed
        estimate_badge = page.locator("[data-testid^='task-estimate-']").first
        expect(estimate_badge).to_contain_text("45 min")

    def test_edit_task_estimated_minutes(self, task_form_page, task_list_page, page):
        """
        Test editing a task's estimated duration.

        User Flow:
        1. Create a task with an estimate
        2. Edit the task
        3. Change the estimated minutes
        4. Verify change is saved
        """
        # Arrange - Create initial task with estimate
        task_form_page.create_task(
            title="Task to Update Estimate",
            estimated_minutes=30
        )

        # Navigate to list and click edit
        task_list_page.navigate()
        page.locator("[data-testid^='edit-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Act - Update the estimated minutes
        task_form_page.fill_estimated_minutes(60)
        task_form_page.submit()

        # Assert
        task_form_page.assert_flash_success_visible()

        # Verify updated estimate in list
        task_list_page.navigate()
        estimate_badge = page.locator("[data-testid^='task-estimate-']").first
        expect(estimate_badge).to_contain_text("60 min")


class TestTaskStatusFlow:
    """Tests for task status management."""

    def test_quick_status_update_from_list(self, task_form_page, task_list_page, page):
        """
        Test updating task status using quick update in list view.

        User Flow:
        1. Create a pending task
        2. Use quick status dropdown to change to completed
        3. Verify status is updated
        """
        # Arrange - Create a pending task
        task_form_page.create_task(
            title="Quick Update Task",
            status="pending"
        )

        # Navigate to list
        task_list_page.navigate()

        # Act - Use quick status update
        status_select = page.locator("[data-testid^='status-select-']").first
        status_select.select_option("completed")
        page.locator("[data-testid^='update-status-btn-']").first.click()
        page.wait_for_load_state("networkidle")

        # Assert
        task_list_page.assert_flash_success_visible()

        # Verify status changed
        status_badge = page.locator("[data-testid^='task-status-']").first
        expect(status_badge).to_contain_text("Completed")
