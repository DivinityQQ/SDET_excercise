"""WSGI entry point for gateway service."""

import os

try:
    from gateway.gateway_app import create_app
except ModuleNotFoundError:  # pragma: no cover - container/service-local fallback
    from gateway_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))
