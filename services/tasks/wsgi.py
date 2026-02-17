"""WSGI entry point for task service."""

import os

try:
    from services.tasks.task_app import create_app
except ModuleNotFoundError:  # pragma: no cover - container/service-local fallback
    from task_app import create_app

app = create_app(os.getenv("FLASK_ENV", "production"))
