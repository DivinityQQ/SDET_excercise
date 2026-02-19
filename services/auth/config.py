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
- JWT-specific settings (private/public keys, expiry, clock skew)
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_key(raw_env_var: str, path_env_var: str) -> str:
    """
    Load a PEM key from raw environment variable or file-path variable.

    The raw PEM variable takes precedence over the path variable so
    orchestrators can inject secrets directly without mounting files.
    """
    raw_key = os.environ.get(raw_env_var, "").strip()
    if raw_key:
        return raw_key

    key_path = os.environ.get(path_env_var, "").strip()
    if key_path:
        try:
            return Path(key_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Unable to read JWT key file at '{key_path}' from {path_env_var}."
            ) from exc

    raise RuntimeError(
        f"Missing JWT key configuration: set {raw_env_var} or {path_env_var}."
    )


def _has_key_source(raw_env_var: str, path_env_var: str) -> bool:
    """Return True when at least one key source variable is configured."""
    return bool(
        os.environ.get(raw_env_var, "").strip()
        or os.environ.get(path_env_var, "").strip()
    )


def load_auth_keys(*, testing: bool) -> tuple[str, str]:
    """
    Resolve auth-service JWT private/public keys for the selected environment.

    In testing mode, TEST_* vars are used when configured; otherwise it falls
    back to the standard JWT_* variables.
    """
    if testing and (
        _has_key_source("TEST_JWT_PRIVATE_KEY", "TEST_JWT_PRIVATE_KEY_PATH")
        or _has_key_source("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH")
    ):
        return (
            _load_key("TEST_JWT_PRIVATE_KEY", "TEST_JWT_PRIVATE_KEY_PATH"),
            _load_key("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH"),
        )

    return (
        _load_key("JWT_PRIVATE_KEY", "JWT_PRIVATE_KEY_PATH"),
        _load_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH"),
    )


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
