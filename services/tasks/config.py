"""
Configuration Classes for the Task Service.

Centralises all environment-dependent settings (database URIs, JWT keys)
into a hierarchy of configuration classes. The base
``Config`` class defines sensible development defaults, while subclasses
override only what differs per environment.

Key Concepts Demonstrated:
- Class-based configuration with inheritance
- Environment-variable overrides for twelve-factor app compliance
- Separate configuration profiles for development, testing, and production
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_key(raw_env_var: str, path_env_var: str) -> str:
    """Load a PEM key from direct env content or from a path env variable."""
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


def load_task_public_key(*, testing: bool) -> str:
    """Resolve task-service JWT public key for the selected environment."""
    if testing and _has_key_source("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH"):
        return _load_key("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH")
    return _load_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH")


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
        JWT_PUBLIC_KEY: Public key used to verify JWTs issued by the
            auth service.
        JWT_CLOCK_SKEW_SECONDS: Allowed clock drift (in seconds) when
            validating JWT ``exp`` / ``iat`` claims.
    """

    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "task-service-dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'tasks.db'}",
    )

    # Tolerate minor clock differences between services when checking exp/iat.
    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))



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
        JWT_PUBLIC_KEY: Test public key for verifying test-minted JWTs.
        WTF_CSRF_ENABLED: Disabled so tests can POST forms without tokens.
    """

    DEBUG: bool = True
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'test_tasks.db'}?check_same_thread=False",
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"pool_pre_ping": True}
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
