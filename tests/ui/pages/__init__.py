"""
Page Object Model (POM) classes for UI testing.

This package contains page objects that encapsulate page-specific
locators and interactions. The POM pattern provides:
- Separation of test logic from page details
- Reusable page interactions
- Maintainable test code (changes to UI only require updates in one place)
"""

from tests.ui.pages.base_page import BasePage
from tests.ui.pages.task_list_page import TaskListPage
from tests.ui.pages.task_form_page import TaskFormPage

__all__ = ["BasePage", "TaskListPage", "TaskFormPage"]
