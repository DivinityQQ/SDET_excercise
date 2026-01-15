"""
Flask application factory module.

This module creates and configures the Flask application using
the factory pattern, allowing for different configurations
(development, testing, production).
"""

import logging
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import get_config

# Initialize SQLAlchemy without binding to app
db = SQLAlchemy()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration environment name.
                     If None, uses FLASK_ENV environment variable.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    logger.info(f"Creating app with config: {config_class.__name__}")

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from app.routes.api import api_bp
    from app.routes.views import views_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(views_bp)

    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")

    return app
