"""
Configuration Classes for the Task Service.

Centralises all environment-dependent settings (database URIs, JWT secrets,
cross-service URLs) into a hierarchy of configuration classes.  The base
``Config`` class defines sensible development defaults, while subclasses
override only what differs per environment.

Key Concepts Demonstrated:
- Class-based configuration with inheritance
- Environment-variable overrides for twelve-factor app compliance
- Separate configuration profiles for development, testing, and production
- Cross-service settings (``AUTH_SERVICE_URL``) for microservice communication
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """
    Base configuration with development-safe defaults.

    All settings can be overridden by environment variables so that the
    same Docker image / code-base can serve any environment by simply
    changing the environment.

    Attributes:
        SECRET_KEY: Flask session signing key.
        SQLALCHEMY_TRACK_MODIFICATIONS: Disabled to save memory.
        SQLALCHEMY_DATABASE_URI: Database connection string (default: local
            SQLite file).
        JWT_SECRET_KEY: Shared secret for verifying JWTs issued by the
            auth service.  Must match the auth service's signing key.
        JWT_CLOCK_SKEW_SECONDS: Allowed clock drift (in seconds) when
            validating JWT ``exp`` / ``iat`` claims.
        AUTH_SERVICE_URL: Base URL of the auth service for cross-service
            HTTP calls (login, registration).
        AUTH_SERVICE_TIMEOUT: Timeout in seconds for HTTP requests to the
            auth service, preventing indefinite hangs if the auth service
            is unresponsive.
    """

    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "task-service-dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'tasks.db'}",
    )

    # JWT shared secret -- must be identical to the value configured on the
    # auth service so that tokens issued there can be verified here.
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "dev-jwt-secret-change-in-production"
    )
    # Tolerate minor clock differences between services when checking exp/iat.
    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))

    # Cross-service communication: the task service calls the auth service
    # for login and registration on behalf of the browser-facing web UI.
    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5010")
    # Guard against slow or unreachable auth service responses.
    AUTH_SERVICE_TIMEOUT: int = int(os.environ.get("AUTH_SERVICE_TIMEOUT", "5"))


class DevelopmentConfig(Config):
    """
    Development environment configuration.

    Enables debug mode for auto-reloading and verbose error pages.
    Inherits all other defaults from ``Config``.
    """

    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """
    Testing environment configuration.

    Uses an isolated SQLite database so that tests do not pollute
    development data.  CSRF protection is disabled to simplify form
    submission in test helpers.

    Attributes:
        SQLALCHEMY_DATABASE_URI: Points to a dedicated test database file.
        JWT_SECRET_KEY: A deterministic test-only secret so that test
            fixtures can mint predictable tokens.
        AUTH_SERVICE_URL: A placeholder URL; tests are expected to mock
            cross-service calls rather than requiring a live auth service.
        AUTH_SERVICE_TIMEOUT: Kept short (1 s) to fail fast in tests.
        WTF_CSRF_ENABLED: Disabled so tests can POST forms without tokens.
    """

    DEBUG: bool = True
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'test_tasks.db'}?check_same_thread=False",
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"pool_pre_ping": True}
    JWT_SECRET_KEY: str = os.environ.get(
        "TEST_JWT_SECRET_KEY", "test-jwt-secret-key-for-local-tests-123456"
    )
    AUTH_SERVICE_URL: str = os.environ.get("TEST_AUTH_SERVICE_URL", "http://auth-service")
    AUTH_SERVICE_TIMEOUT: int = int(os.environ.get("TEST_AUTH_SERVICE_TIMEOUT", "1"))
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(Config):
    """
    Production environment configuration.

    Disables debug mode and testing flags.  All secrets and URIs should
    be supplied exclusively through environment variables in production.
    """

    DEBUG: bool = False
    TESTING: bool = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    """
    Look up and return the configuration class for the given environment.

    Args:
        env: Environment name (``"development"``, ``"testing"``,
            ``"production"``).  When ``None``, falls back to the
            ``FLASK_ENV`` environment variable, defaulting to
            ``"development"``.

    Returns:
        The configuration class (not an instance) corresponding to the
        requested environment.
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
