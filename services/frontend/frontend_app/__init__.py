"""
Frontend service Flask application factory.

Provides the ``create_app`` factory function that assembles the frontend
micro-service.  This service acts as a stateless Backend-for-Frontend (BFF):
it serves server-rendered HTML pages via Jinja templates and orchestrates
calls to the auth and task REST APIs on behalf of the browser.

The BFF never accesses a database directly -- all persistence is delegated
to the downstream micro-services, keeping this layer thin and focused on
presentation concerns (form handling, flash messages, session cookies).

Key Concepts Demonstrated:
- Application factory pattern (``create_app``)
- Backend-for-Frontend (BFF) architecture
- Server-side session management with JWT tokens
- Blueprint-based route registration
- Lazy import to avoid circular dependencies
"""

from __future__ import annotations

import logging

from flask import Flask

try:
    from services.frontend.config import get_config, load_frontend_public_key
except ModuleNotFoundError:  # pragma: no cover - fallback for service-local execution
    from config import get_config, load_frontend_public_key


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure the frontend service application.

    Instantiates the Flask app, loads the appropriate configuration object,
    reads the JWT public key (used to verify session tokens issued by the
    auth service), and registers the views blueprint.

    Args:
        config_name: Optional configuration environment name
            (``"development"``, ``"testing"``, ``"production"``).  When
            *None*, the value is read from the ``FLASK_ENV`` environment
            variable, defaulting to ``"development"``.

    Returns:
        A fully configured :class:`~flask.Flask` application instance
        ready to serve HTML pages and proxy API requests.
    """
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config["JWT_PUBLIC_KEY"] = load_frontend_public_key(
        testing=bool(app.config.get("TESTING"))
    )

    logger.info("Creating frontend service app with config: %s", config_class.__name__)

    # Import inside the factory to avoid circular imports -- the blueprint
    # module references helpers from this package, which must exist first.
    from .routes.views import views_bp

    app.register_blueprint(views_bp)
    return app
