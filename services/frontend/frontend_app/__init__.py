"""
Frontend service Flask application factory.

This service is a stateless BFF that serves server-rendered pages and
orchestrates calls to the auth and task APIs.
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

    Args:
        config_name: Optional config environment key.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config["JWT_PUBLIC_KEY"] = load_frontend_public_key(
        testing=bool(app.config.get("TESTING"))
    )

    logger.info("Creating frontend service app with config: %s", config_class.__name__)

    from .routes.views import views_bp

    app.register_blueprint(views_bp)
    return app
