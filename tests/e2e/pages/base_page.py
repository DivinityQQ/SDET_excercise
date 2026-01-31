"""
Base Page class for the Page Object Model.

This class provides common functionality shared by all page objects,
including navigation, common locators, and utility methods.

Key Concepts Demonstrated:
- Base class pattern for code reuse
- Locator strategies (data-testid, CSS, text)
- Common actions (wait, click, fill)
- Assertion helpers
"""

from playwright.sync_api import Page, Locator, expect


class BasePage:
    """
    Base class for all page objects.

    Provides common functionality and locators shared across pages.
    All page objects should inherit from this class.

    Attributes:
        page: Playwright page instance.
        base_url: Base URL of the application.
    """

    def __init__(self, page: Page, base_url: str):
        """
        Initialize the base page.

        Args:
            page: Playwright page instance.
            base_url: Base URL of the application.
        """
        self.page = page
        self.base_url = base_url

    # -------------------------------------------------------------------------
    # Common Locators
    # -------------------------------------------------------------------------

    @property
    def nav_home(self) -> Locator:
        """Locator for the home navigation link."""
        return self.page.get_by_test_id("nav-home")

    @property
    def nav_new_task(self) -> Locator:
        """Locator for the new task navigation link."""
        return self.page.get_by_test_id("nav-new-task")

    @property
    def flash_messages(self) -> Locator:
        """Locator for flash messages container."""
        return self.page.get_by_test_id("flash-messages")

    @property
    def flash_success(self) -> Locator:
        """Locator for success flash messages."""
        return self.page.get_by_test_id("flash-success")

    @property
    def flash_error(self) -> Locator:
        """Locator for error flash messages."""
        return self.page.get_by_test_id("flash-error")

    # -------------------------------------------------------------------------
    # Navigation Methods
    # -------------------------------------------------------------------------

    def navigate_to(self, path: str = "") -> None:
        """
        Navigate to a specific path.

        Args:
            path: URL path relative to base URL.
        """
        url = f"{self.base_url}{path}"
        self.page.goto(url)

    def click_home(self) -> None:
        """Navigate to home page via nav link."""
        self.nav_home.click()

    def click_new_task(self) -> None:
        """Navigate to new task form via nav link."""
        self.nav_new_task.click()

    # -------------------------------------------------------------------------
    # Wait Methods
    # -------------------------------------------------------------------------

    def wait_for_page_load(self) -> None:
        """Wait for page to finish loading."""
        self.page.wait_for_load_state("networkidle")

    def wait_for_element(self, locator: Locator, timeout: int = 5000) -> None:
        """
        Wait for an element to be visible.

        Args:
            locator: Playwright locator for the element.
            timeout: Maximum wait time in milliseconds.
        """
        locator.wait_for(state="visible", timeout=timeout)

    # -------------------------------------------------------------------------
    # Assertion Methods
    # -------------------------------------------------------------------------

    def assert_url_contains(self, expected: str) -> None:
        """
        Assert that current URL contains expected string.

        Args:
            expected: String expected to be in the URL.
        """
        import re
        # Use regex for more flexible matching
        expect(self.page).to_have_url(re.compile(re.escape(expected)))

    def assert_flash_success_visible(self) -> None:
        """Assert that a success flash message is visible."""
        expect(self.flash_success).to_be_visible()

    def assert_flash_error_visible(self) -> None:
        """Assert that an error flash message is visible."""
        expect(self.flash_error).to_be_visible()

    def assert_flash_contains(self, text: str) -> None:
        """
        Assert that flash messages contain specific text.

        Args:
            text: Expected text in flash messages.
        """
        expect(self.flash_messages).to_contain_text(text)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_by_test_id(self, test_id: str) -> Locator:
        """
        Get element by data-testid attribute.

        This is the preferred locator strategy as data-testid
        attributes are stable and designed for testing.

        Args:
            test_id: Value of the data-testid attribute.

        Returns:
            Locator for the element.
        """
        return self.page.get_by_test_id(test_id)

    def take_screenshot(self, name: str) -> str:
        """
        Take a screenshot of the current page.

        Args:
            name: Name for the screenshot file.

        Returns:
            Path to the saved screenshot.
        """
        import os
        screenshot_dir = "test-results/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        path = f"{screenshot_dir}/{name}.png"
        self.page.screenshot(path=path)
        return path
