"""
Configuration for the auth service.

Provides environment-aware configuration classes that follow Flask's
recommended pattern: a shared ``Config`` base class holds defaults, and
environment-specific subclasses (``DevelopmentConfig``, ``TestingConfig``,
``ProductionConfig``) override only what differs.  The ``get_config``
factory resolves the correct class at runtime based on an environment
variable or an explicit argument, making it easy to switch profiles
without touching application code.

Key Concepts Demonstrated:
- Inheritance-based configuration hierarchy
- Environment variable overrides with sensible defaults
- Separate database for testing to protect development data
- JWT-specific settings (secret, expiry, clock skew)
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """
    Base configuration shared by all environments.

    Subclasses should override only the values that need to change.
    Every setting can also be controlled via an environment variable so
    that container orchestrators can inject secrets at deploy time.
    """

    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "auth-service-dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'auth.db'}",
    )

    # The HMAC secret used to sign and verify JWTs.  Must be identical
    # across every service that needs to verify tokens.
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "dev-jwt-secret-change-in-production"
    )
    # How many hours a newly issued token remains valid before expiring
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    # Seconds of tolerance for clock differences between issuer and verifier
    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))


class DevelopmentConfig(Config):
    """
    Configuration for local development.

    Enables debug mode for auto-reload and rich tracebacks while keeping
    ``TESTING`` off so that Flask error handlers behave normally.
    """

    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """
    Configuration for the automated test suite.

    Uses a **separate** SQLite database (``test_auth.db``) so that test
    runs never corrupt development data.  ``TESTING = True`` causes Flask
    to propagate exceptions instead of returning HTML error pages, making
    assertion failures more obvious.
    """

    DEBUG: bool = True
    TESTING: bool = True
    # Separate database file prevents test pollution of development data.
    # ``check_same_thread=False`` is required because SQLite normally
    # forbids sharing a connection across threads, but Flask's test client
    # may operate from a different thread than the one that opened the DB.
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'test_auth.db'}?check_same_thread=False",
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"pool_pre_ping": True}
    # Shorter-lived test secret and expiry to keep tests fast and isolated
    JWT_SECRET_KEY: str = os.environ.get(
        "TEST_JWT_SECRET_KEY", "test-jwt-secret-key-for-local-tests-123456"
    )
    JWT_EXPIRY_HOURS: int = int(os.environ.get("TEST_JWT_EXPIRY_HOURS", "1"))


class ProductionConfig(Config):
    """
    Configuration for production deployments.

    Disables debug mode and testing flags.  All secrets **must** be
    supplied through environment variables -- the hard-coded defaults in
    the base ``Config`` class are intentionally insecure to ensure they
    are never accidentally used in production.
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
    Resolve a configuration class by environment name.

    Args:
        env: One of ``"development"``, ``"testing"``, or
            ``"production"``.  When ``None``, the ``FLASK_ENV``
            environment variable is consulted, falling back to
            ``"development"`` if unset.

    Returns:
        The configuration class (not an instance) corresponding to the
        requested environment.  Falls back to ``DevelopmentConfig`` for
        unrecognised names.
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
