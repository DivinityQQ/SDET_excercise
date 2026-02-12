"""
Gateway Service — Application Factory.

This module provides the Flask application factory for the API gateway
service.  The gateway acts as a single entry-point (reverse proxy) for
all client traffic, forwarding requests to the appropriate downstream
microservice (auth-service, task-service) and returning their responses.

Key Concepts Demonstrated:
- Application Factory pattern (create_app) for flexible configuration
- Blueprint registration for modular route organisation
- Environment-aware configuration loading via get_config
"""

from __future__ import annotations

import logging

from flask import Flask

try:
    from gateway.config import get_config
except ModuleNotFoundError:  # pragma: no cover - fallback for service-local execution
    from config import get_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Construct and configure the gateway Flask application.

    This factory wires together configuration, logging, and the proxy
    route blueprint so that each test or deployment can receive a fresh,
    independently-configured application instance.

    Args:
        config_name: Optional environment key ("development", "testing",
            "production").  When *None*, the FLASK_ENV environment
            variable is consulted, defaulting to "development".

    Returns:
        A fully-configured Flask application with the gateway blueprint
        registered and ready to proxy requests.
    """
    app = Flask(__name__)
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    logger.info("Creating gateway app with config: %s", config_class.__name__)

    # Import inside the factory to avoid circular imports — the blueprint
    # references current_app, which requires an active application context.
    from gateway_app.routes import gateway_bp

    app.register_blueprint(gateway_bp)
    return app
