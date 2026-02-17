"""Login page object for E2E authentication flows."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from tests.e2e.pages.base_page import BasePage


class LoginPage(BasePage):
    """
    Page object for the login page.

    Provides methods for:
    - Entering credentials
    - Submitting the login form
    - Navigating to registration
    """

    URL_PATH = "/login"

    def __init__(self, page: Page, base_url: str):
        """
        Initialize LoginPage.

        Args:
            page: Playwright page instance.
            base_url: Base URL of the application.
        """
        super().__init__(page, base_url)

    def navigate(self) -> "LoginPage":
        """
        Navigate to the login page.

        Returns:
            Self for method chaining.
        """
        self.navigate_to(self.URL_PATH)
        self.wait_for_page_load()
        return self

    @property
    def username_input(self) -> Locator:
        """Locator for the username input field."""
        return self.get_by_test_id("login-username-input")

    @property
    def password_input(self) -> Locator:
        """Locator for the password input field."""
        return self.get_by_test_id("login-password-input")

    @property
    def submit_button(self) -> Locator:
        """Locator for the login submit button."""
        return self.get_by_test_id("login-submit")

    @property
    def register_link(self) -> Locator:
        """Locator for the register navigation link."""
        return self.get_by_test_id("register-link")

    def login(self, username: str, password: str) -> None:
        """
        Fill credentials and submit the login form.

        Args:
            username: Username to enter.
            password: Password to enter.
        """
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()
        self.wait_for_page_load()
