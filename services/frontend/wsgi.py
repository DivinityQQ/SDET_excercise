"""WSGI entry point for frontend service."""

import os

from frontend_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))
