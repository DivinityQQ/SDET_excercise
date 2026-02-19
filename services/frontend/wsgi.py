"""WSGI entry point for frontend service."""

import os

try:
    from services.frontend.frontend_app import create_app
except ModuleNotFoundError:  # pragma: no cover - container/service-local fallback
    from frontend_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))
