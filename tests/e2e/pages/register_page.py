"""Register page object for E2E authentication flows."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from tests.e2e.pages.base_page import BasePage


class RegisterPage(BasePage):
    """
    Page object for the registration page.

    Provides methods for:
    - Filling registration fields
    - Submitting the registration form
    - Navigating to login
    """

    URL_PATH = "/register"

    def __init__(self, page: Page, base_url: str):
        """
        Initialize RegisterPage.

        Args:
            page: Playwright page instance.
            base_url: Base URL of the application.
        """
        super().__init__(page, base_url)

    def navigate(self) -> "RegisterPage":
        """
        Navigate to the registration page.

        Returns:
            Self for method chaining.
        """
        self.navigate_to(self.URL_PATH)
        self.wait_for_page_load()
        return self

    @property
    def username_input(self) -> Locator:
        """Locator for the username input field."""
        return self.get_by_test_id("register-username-input")

    @property
    def email_input(self) -> Locator:
        """Locator for the email input field."""
        return self.get_by_test_id("register-email-input")

    @property
    def password_input(self) -> Locator:
        """Locator for the password input field."""
        return self.get_by_test_id("register-password-input")

    @property
    def submit_button(self) -> Locator:
        """Locator for the registration submit button."""
        return self.get_by_test_id("register-submit")

    @property
    def login_link(self) -> Locator:
        """Locator for the login navigation link."""
        return self.get_by_test_id("login-link")

    def register(self, username: str, email: str, password: str) -> None:
        """
        Fill all fields and submit the registration form.

        Args:
            username: Username to enter.
            email: Email address to enter.
            password: Password to enter.
        """
        self.username_input.fill(username)
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.submit_button.click()
        self.wait_for_page_load()
