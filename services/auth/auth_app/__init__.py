"""
Auth service Flask application factory.

Provides the ``create_app`` factory function used to build and configure the
Flask application that powers the authentication micro-service.  The factory
pattern allows different configurations (development, testing, production) to
be injected at runtime, which is essential for isolated test suites and
container-based deployments.

Key Concepts Demonstrated:
- Application factory pattern (create_app)
- Flask extension initialisation (SQLAlchemy)
- Blueprint-based route registration
- Lazy import to avoid circular dependencies
"""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

try:
    from services.auth.config import get_config, load_auth_keys
except ModuleNotFoundError:  # pragma: no cover - fallback for service-local execution
    from config import get_config, load_auth_keys


# Shared SQLAlchemy instance -- initialised with a concrete app inside create_app()
db = SQLAlchemy()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure the auth service Flask application.

    This is the canonical entry-point for standing up the auth service.
    It wires together configuration, extensions, blueprints, and the
    database schema in a deterministic order so that every consumer
    (WSGI server, test harness, CLI) gets an identical application
    instance for a given configuration name.

    Args:
        config_name: The configuration environment to load (e.g.
            ``"development"``, ``"testing"``, ``"production"``).  When
            ``None``, the value is resolved from the ``FLASK_ENV``
            environment variable, defaulting to ``"development"``.

    Returns:
        A fully configured :class:`~flask.Flask` application instance
        with all extensions initialised and database tables created.
    """
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    private_key, public_key = load_auth_keys(testing=bool(app.config.get("TESTING")))
    app.config["JWT_PRIVATE_KEY"] = private_key
    app.config["JWT_PUBLIC_KEY"] = public_key

    logger.info("Creating auth service app with config: %s", config_class.__name__)

    # Ensure the instance directory exists for the SQLite database file
    os.makedirs(app.instance_path, exist_ok=True)

    # Bind the shared SQLAlchemy instance to this application
    db.init_app(app)

    # Import inside the factory to avoid circular imports -- the blueprint
    # module references ``db`` from this package, which must exist first.
    from .routes.api import api_bp

    # Mount all auth endpoints under /api/auth so the gateway can proxy cleanly
    app.register_blueprint(api_bp, url_prefix="/api/auth")

    # Create tables within an application context so SQLAlchemy knows which
    # engine to bind to.  In production this would typically be handled by a
    # migration tool such as Alembic.
    with app.app_context():
        db.create_all()
        logger.info("Auth service database tables created")

    return app
