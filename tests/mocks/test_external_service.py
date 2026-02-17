"""
Mocking Examples for External Service Integration.

This module demonstrates various mocking techniques commonly used
in SDET work. While our Task Manager doesn't have real external
services, these examples show how you would test code that does.

Key SDET Concepts Demonstrated:
- unittest.mock basics (patch, MagicMock)
- Mocking HTTP requests
- Mocking return values
- Mocking side effects (exceptions)
- Verifying mock calls
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime


pytestmark = pytest.mark.unit


# =============================================================================
# Example: Simulated External Service
# =============================================================================

class NotificationService:
    """
    Example external service for sending notifications.

    In a real application, this might send emails, SMS, or
    push notifications. We'll use mocking to test code that
    depends on this service without actually sending notifications.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.notifications.example.com"

    def send_email(self, to: str, subject: str, body: str) -> dict:
        """
        Send an email notification.

        In reality, this would make an HTTP request to an
        external API.

        Args:
            to: Email recipient.
            subject: Email subject.
            body: Email body.

        Returns:
            API response with message ID.
        """
        # This would normally call an external API
        import requests
        response = requests.post(
            f"{self.base_url}/email",
            json={"to": to, "subject": subject, "body": body},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()

    def send_sms(self, phone: str, message: str) -> dict:
        """Send an SMS notification."""
        import requests
        response = requests.post(
            f"{self.base_url}/sms",
            json={"phone": phone, "message": message},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()


class TaskNotifier:
    """
    Service that sends notifications about task events.

    This class depends on NotificationService and is what
    we'll test using mocking.
    """

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    def notify_task_created(self, task_title: str, assignee_email: str) -> bool:
        """
        Send notification when a task is created.

        Args:
            task_title: Title of the created task.
            assignee_email: Email of the person assigned.

        Returns:
            True if notification sent successfully.
        """
        try:
            result = self.notification_service.send_email(
                to=assignee_email,
                subject=f"New Task: {task_title}",
                body=f"You have been assigned a new task: {task_title}"
            )
            return "message_id" in result
        except Exception:
            return False

    def notify_task_overdue(self, task_title: str, phone: str) -> bool:
        """Send SMS notification for overdue task."""
        try:
            result = self.notification_service.send_sms(
                phone=phone,
                message=f"OVERDUE: {task_title}"
            )
            return "message_id" in result
        except Exception:
            return False


# =============================================================================
# Mocking Tests
# =============================================================================

class TestMockingBasics:
    """Basic mocking examples."""

    def test_mock_return_value(self):
        """
        Example: Mocking a method's return value.

        Use when you want to control what a method returns
        without executing its real implementation.
        """
        # Arrange - Create mock service
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.return_value = {"message_id": "123", "status": "sent"}

        notifier = TaskNotifier(mock_service)

        # Act
        result = notifier.notify_task_created(
            task_title="Test Task",
            assignee_email="user@example.com"
        )

        # Assert
        assert result is True
        mock_service.send_email.assert_called_once()

    def test_mock_with_specific_arguments(self):
        """
        Example: Verifying mock was called with specific arguments.

        Use when you need to verify the exact parameters
        passed to a dependency.
        """
        # Arrange
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.return_value = {"message_id": "456"}

        notifier = TaskNotifier(mock_service)

        # Act
        notifier.notify_task_created(
            task_title="Important Task",
            assignee_email="boss@example.com"
        )

        # Assert - Verify exact arguments
        mock_service.send_email.assert_called_once_with(
            to="boss@example.com",
            subject="New Task: Important Task",
            body="You have been assigned a new task: Important Task"
        )

    def test_mock_side_effect_exception(self):
        """
        Example: Mocking to simulate an exception.

        Use when testing error handling for external
        service failures.
        """
        # Arrange - Mock raises exception
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.side_effect = ConnectionError("Service unavailable")

        notifier = TaskNotifier(mock_service)

        # Act
        result = notifier.notify_task_created(
            task_title="Test Task",
            assignee_email="user@example.com"
        )

        # Assert - Should handle error gracefully
        assert result is False

    def test_mock_multiple_return_values(self):
        """
        Example: Different return values for consecutive calls.

        Use when testing retry logic or sequences of calls.
        """
        # Arrange - First call fails, second succeeds
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.side_effect = [
            {"error": "temporary failure"},  # First call
            {"message_id": "789"}            # Second call (retry)
        ]

        # Act - Simulate two calls
        result1 = mock_service.send_email("a@b.com", "Subject", "Body")
        result2 = mock_service.send_email("a@b.com", "Subject", "Body")

        # Assert
        assert "error" in result1
        assert "message_id" in result2


class TestPatchDecorator:
    """Examples using the @patch decorator."""

    @patch("tests.mocks.test_external_service.NotificationService")
    def test_patch_class(self, MockNotificationService):
        """
        Example: Patching an entire class.

        Use when you want to replace a class with a mock
        in the module under test.
        """
        # Arrange
        mock_instance = MockNotificationService.return_value
        mock_instance.send_email.return_value = {"message_id": "test123"}

        # Act - Code that creates NotificationService will get mock
        service = NotificationService("fake-api-key")
        result = service.send_email("to@example.com", "Subject", "Body")

        # Assert
        assert result["message_id"] == "test123"

    @patch("requests.post")
    def test_patch_requests(self, mock_post):
        """
        Example: Patching the requests library.

        This is the most common pattern for mocking HTTP calls.
        """
        # Arrange - Configure mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"message_id": "http123", "status": "delivered"}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Act - Make the "real" call (actually goes to mock)
        service = NotificationService("test-api-key")
        result = service.send_email("to@test.com", "Test Subject", "Test Body")

        # Assert
        assert result["message_id"] == "http123"
        mock_post.assert_called_once()

        # Verify the URL that would have been called
        call_args = mock_post.call_args
        assert "email" in call_args[0][0]  # URL contains 'email'


class TestMockingWithContext:
    """Examples using patch as context manager."""

    def test_patch_context_manager(self):
        """
        Example: Using patch as a context manager.

        Use when you want fine-grained control over when
        mocking is active.
        """
        # Arrange
        service = NotificationService("real-api-key")

        # Mock is only active within the 'with' block
        with patch.object(service, "send_email") as mock_send:
            mock_send.return_value = {"message_id": "context123"}

            # Act
            result = service.send_email("to@test.com", "Subject", "Body")

            # Assert
            assert result["message_id"] == "context123"
            mock_send.assert_called_once()

    def test_mock_datetime(self):
        """
        Example: Mocking datetime for time-sensitive tests.

        Use when testing code that depends on current time.
        """
        # Arrange
        fixed_time = datetime(2025, 1, 15, 10, 30, 0)

        with patch("tests.mocks.test_external_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Act
            from tests.mocks.test_external_service import datetime as dt

            # Assert
            assert dt.now() == fixed_time


class TestVerifyingCalls:
    """Examples of verifying mock interactions."""

    def test_verify_call_count(self):
        """
        Example: Verifying how many times a mock was called.

        Use when testing that a service is called the
        expected number of times.
        """
        # Arrange
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.return_value = {"message_id": "test"}

        notifier = TaskNotifier(mock_service)

        # Act - Send multiple notifications
        notifier.notify_task_created("Task 1", "user1@example.com")
        notifier.notify_task_created("Task 2", "user2@example.com")
        notifier.notify_task_created("Task 3", "user3@example.com")

        # Assert
        assert mock_service.send_email.call_count == 3

    def test_verify_call_order(self):
        """
        Example: Verifying the order of mock calls.

        Use when the sequence of operations matters.
        """
        # Arrange
        mock_service = MagicMock(spec=NotificationService)
        mock_service.send_email.return_value = {"message_id": "test"}
        mock_service.send_sms.return_value = {"message_id": "test"}

        notifier = TaskNotifier(mock_service)

        # Act
        notifier.notify_task_created("Task", "email@example.com")
        notifier.notify_task_overdue("Task", "+1234567890")

        # Assert - Verify call order
        expected_calls = [
            call.send_email(
                to="email@example.com",
                subject="New Task: Task",
                body="You have been assigned a new task: Task"
            ),
            call.send_sms(
                phone="+1234567890",
                message="OVERDUE: Task"
            )
        ]
        mock_service.assert_has_calls(expected_calls, any_order=False)

    def test_verify_no_calls(self):
        """
        Example: Verifying a mock was NOT called.

        Use when testing that certain paths don't
        trigger external calls.
        """
        # Arrange
        mock_service = MagicMock(spec=NotificationService)

        # Act - Don't call anything

        # Assert
        mock_service.send_email.assert_not_called()
        mock_service.send_sms.assert_not_called()


def _call_auth_service_login(auth_base_url: str, username: str, password: str, timeout: int = 5) -> dict:
    """Example helper showing how task views can call auth-service over HTTP."""
    import requests

    response = requests.post(
        f"{auth_base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


class TestMockAuthServiceCalls:
    """Examples for mocking auth-service calls from another service."""

    @patch("requests.post")
    def test_mock_auth_login_http_call(self, mock_post):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "token": "jwt-token",
            "user": {"id": 1, "username": "demo"},
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        result = _call_auth_service_login(
            auth_base_url="http://auth-service:5000",
            username="demo",
            password="secret",
            timeout=3,
        )

        # Assert
        assert result["token"] == "jwt-token"
        mock_post.assert_called_once_with(
            "http://auth-service:5000/api/auth/login",
            json={"username": "demo", "password": "secret"},
            timeout=3,
        )
