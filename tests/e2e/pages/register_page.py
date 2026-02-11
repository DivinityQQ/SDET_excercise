"""Register page object for E2E authentication flows."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from tests.e2e.pages.base_page import BasePage


class RegisterPage(BasePage):
    URL_PATH = "/register"

    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def navigate(self) -> "RegisterPage":
        self.navigate_to(self.URL_PATH)
        self.wait_for_page_load()
        return self

    @property
    def username_input(self) -> Locator:
        return self.get_by_test_id("register-username-input")

    @property
    def email_input(self) -> Locator:
        return self.get_by_test_id("register-email-input")

    @property
    def password_input(self) -> Locator:
        return self.get_by_test_id("register-password-input")

    @property
    def submit_button(self) -> Locator:
        return self.get_by_test_id("register-submit")

    @property
    def login_link(self) -> Locator:
        return self.get_by_test_id("login-link")

    def register(self, username: str, email: str, password: str) -> None:
        self.username_input.fill(username)
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.submit_button.click()
        self.wait_for_page_load()

