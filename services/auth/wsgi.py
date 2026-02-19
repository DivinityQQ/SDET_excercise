"""WSGI entry point for auth service."""

import os

try:
    from services.auth.auth_app import create_app
except ModuleNotFoundError:  # pragma: no cover - container/service-local fallback
    from auth_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))
