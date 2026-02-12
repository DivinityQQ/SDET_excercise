"""
Task Service Flask Application Factory.

Provides the ``create_app`` factory function that assembles the task
micro-service.  The factory pattern allows multiple application instances
with different configurations (development, testing, production) to coexist
in the same process -- essential for parallel test execution.

The service registers two blueprints:
  * **api_bp** -- JSON REST endpoints mounted at ``/api`` (consumed by
    programmatic clients and the test-suite).
  * **views_bp** -- HTML/template routes mounted at ``/`` (the browser-facing
    web UI that delegates authentication to the auth service).

Key Concepts Demonstrated:
- Application factory pattern (``create_app``)
- Dual-blueprint architecture (API + server-rendered views)
- SQLAlchemy integration with Flask via ``flask_sqlalchemy``
"""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

try:
    from services.tasks.config import get_config, load_task_public_key
except ModuleNotFoundError:  # pragma: no cover - fallback for service-local execution
    from config import get_config, load_task_public_key


db = SQLAlchemy()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure the task service application.

    Instantiates the Flask app, loads the appropriate configuration object,
    initialises extensions (SQLAlchemy), registers the API and view blueprints,
    and ensures that all database tables exist.

    Args:
        config_name: Optional configuration environment name
            (``"development"``, ``"testing"``, ``"production"``).  When *None*,
            the value is read from the ``FLASK_ENV`` environment variable,
            defaulting to ``"development"``.

    Returns:
        A fully configured Flask application instance ready to serve requests.
    """
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config["JWT_PUBLIC_KEY"] = load_task_public_key(testing=bool(app.config.get("TESTING")))

    logger.info("Creating task service app with config: %s", config_class.__name__)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from .routes.api import api_bp
    from .routes.views import views_bp

    # Register the REST API blueprint under /api -- all programmatic endpoints
    # (CRUD for tasks, health-check) live here.
    app.register_blueprint(api_bp, url_prefix="/api")

    # Register the HTML views blueprint at the root -- serves the browser UI
    # (login, register, task list pages) and performs cross-service calls to
    # the auth service for credential verification.
    app.register_blueprint(views_bp)

    with app.app_context():
        db.create_all()
        logger.info("Task service database tables created")

    return app
