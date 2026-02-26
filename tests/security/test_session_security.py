"""Security tests for frontend session cookie hardening."""

from __future__ import annotations

import pytest

from services.frontend.config import ProductionConfig

try:
    from services.frontend.frontend_app.routes import views as views_module
except ModuleNotFoundError:  # pragma: no cover - service-local fallback
    from frontend_app.routes import views as views_module

pytestmark = pytest.mark.security


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_frontend_cookie_flags_are_hardened(frontend_service_app):
    """Frontend should enforce secure defaults on session cookie flags."""
    assert frontend_service_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert frontend_service_app.config["SESSION_COOKIE_SAMESITE"] in {"Lax", "Strict"}


def test_production_enables_secure_session_cookie_flag():
    """Production config should require HTTPS-only session cookies by default."""
    assert ProductionConfig.SESSION_COOKIE_SECURE is True


def test_login_sets_httponly_and_samesite_cookie(frontend_client, monkeypatch):
    """Successful login should emit a hardened session cookie."""
    monkeypatch.setattr(
        views_module.requests,
        "post",
        lambda *_, **__: _FakeResponse(
            status_code=200,
            payload={"token": "fake.jwt.token", "user": {"id": 1, "username": "demo"}},
        ),
    )

    response = frontend_client.post(
        "/login",
        data={"username": "demo", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    set_cookie_headers = response.headers.getlist("Set-Cookie")
    session_cookie = next((h for h in set_cookie_headers if h.startswith("session=")), "")
    assert session_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie
