"""
Security tests for stored XSS-safe rendering in frontend templates.

Injects classic XSS payloads (script tags, event-handler attributes) into
task data via a monkeypatched API response and verifies that Jinja2's
auto-escaping converts them to harmless HTML entities in the rendered
output (OWASP A03 – Injection / A07 – Cross-Site Scripting).

Key SDET Concepts Demonstrated:
- Monkeypatching external HTTP calls to inject controlled malicious data
- HTML entity verification for output-encoding correctness
- Multi-vector XSS coverage (inline script, event-handler attribute)
"""

from __future__ import annotations

import pytest

from shared.test_helpers import TEST_PRIVATE_KEY, create_test_token

try:
    from services.frontend.frontend_app.routes import views as views_module
except ModuleNotFoundError:  # pragma: no cover - service-local fallback
    from frontend_app.routes import views as views_module

pytestmark = pytest.mark.security


class _FakeResponse:
    """Minimal stand-in for ``requests.Response`` used by monkeypatched calls."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _task_payload(*, task_id: int, title: str, description: str) -> dict:
    """Build a realistic task API response dict with the given user-controlled fields."""
    return {
        "id": task_id,
        "user_id": 1,
        "title": title,
        "description": description,
        "status": "pending",
        "priority": "medium",
        "due_date": None,
        "estimated_minutes": None,
        "created_at": "2026-01-01T10:00:00+00:00",
        "updated_at": "2026-01-01T10:00:00+00:00",
    }


def test_index_escapes_script_payloads(frontend_client, monkeypatch):
    """Task titles containing script tags must be HTML-escaped in index view."""
    # Arrange — seed a session and prepare a malicious task title
    token = create_test_token(user_id=1, username="xss_user", private_key=TEST_PRIVATE_KEY)
    with frontend_client.session_transaction() as session:
        session["auth_token"] = token

    malicious_title = "<script>alert(1)</script>"

    def _fake_request(**kwargs):
        assert kwargs["method"] == "GET"
        return _FakeResponse(
            status_code=200,
            payload={
                "tasks": [_task_payload(task_id=1, title=malicious_title, description="safe")],
                "count": 1,
            },
        )

    monkeypatch.setattr(views_module.requests, "request", _fake_request)

    # Act
    response = frontend_client.get("/")

    # Assert — raw script tag must not appear; escaped entity must
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert malicious_title not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_task_detail_escapes_event_handler_payloads(frontend_client, monkeypatch):
    """Task descriptions containing HTML event handlers must render escaped."""
    # Arrange — seed a session and prepare an event-handler XSS vector
    token = create_test_token(user_id=1, username="xss_user", private_key=TEST_PRIVATE_KEY)
    with frontend_client.session_transaction() as session:
        session["auth_token"] = token

    malicious_description = "<img src=x onerror=alert(1)>"

    def _fake_request(**kwargs):
        assert kwargs["method"] == "GET"
        if kwargs["url"].endswith("/api/tasks/1"):
            return _FakeResponse(
                status_code=200,
                payload=_task_payload(
                    task_id=1,
                    title="Safe title",
                    description=malicious_description,
                ),
            )
        return _FakeResponse(status_code=500, payload={"error": "unexpected path"})

    monkeypatch.setattr(views_module.requests, "request", _fake_request)

    # Act
    response = frontend_client.get("/tasks/1")

    # Assert — raw img/onerror tag must not appear; escaped entity must
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert malicious_description not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
