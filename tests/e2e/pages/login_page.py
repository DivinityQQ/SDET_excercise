"""Login page object for E2E authentication flows."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from tests.e2e.pages.base_page import BasePage


class LoginPage(BasePage):
    URL_PATH = "/login"

    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def navigate(self) -> "LoginPage":
        self.navigate_to(self.URL_PATH)
        self.wait_for_page_load()
        return self

    @property
    def username_input(self) -> Locator:
        return self.get_by_test_id("login-username-input")

    @property
    def password_input(self) -> Locator:
        return self.get_by_test_id("login-password-input")

    @property
    def submit_button(self) -> Locator:
        return self.get_by_test_id("login-submit")

    @property
    def register_link(self) -> Locator:
        return self.get_by_test_id("register-link")

    def login(self, username: str, password: str) -> None:
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()
        self.wait_for_page_load()

