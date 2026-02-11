"""Gateway Flask application factory."""

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
    app = Flask(__name__)
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    logger.info("Creating gateway app with config: %s", config_class.__name__)

    from gateway_app.routes import gateway_bp

    app.register_blueprint(gateway_bp)
    return app

