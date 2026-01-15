"""
Application configuration module.

This module defines configuration classes for different environments
(development, testing, production). Configuration values are loaded
from environment variables with sensible defaults.
"""

import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration with default settings."""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Default database location
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'tasks.db'}"
    )


class DevelopmentConfig(Config):
    """Development environment configuration."""

    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """Testing environment configuration."""

    DEBUG: bool = True
    TESTING: bool = True

    # Use separate test database with check_same_thread=False for multi-threaded access
    # This is needed for Playwright UI tests where the server runs in a separate thread
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'test_tasks.db'}?check_same_thread=False"
    )

    # SQLAlchemy engine options for thread safety
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
    }

    # Disable CSRF for testing
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(Config):
    """Production environment configuration."""

    DEBUG: bool = False
    TESTING: bool = False


# Configuration mapping for easy access
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    """
    Get the configuration class for the specified environment.

    Args:
        env: Environment name (development, testing, production).
             If None, uses FLASK_ENV environment variable.

    Returns:
        Configuration class for the specified environment.
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
