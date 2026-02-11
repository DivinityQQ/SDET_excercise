"""Task service Flask application factory."""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

try:
    from services.tasks.config import get_config
except ModuleNotFoundError:  # pragma: no cover - fallback for service-local execution
    from config import get_config


db = SQLAlchemy()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the task service application."""
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    logger.info("Creating task service app with config: %s", config_class.__name__)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from task_app.routes.api import api_bp
    from task_app.routes.views import views_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(views_bp)

    with app.app_context():
        db.create_all()
        logger.info("Task service database tables created")

    return app

