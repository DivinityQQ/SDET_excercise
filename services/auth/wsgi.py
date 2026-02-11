"""WSGI entry point for auth service."""

import os

from auth_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))

