"""WSGI entry point for gateway service."""

import os

from gateway_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))

