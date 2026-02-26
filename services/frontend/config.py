"""
Configuration classes for the frontend service.

The frontend service is a stateless BFF (backend-for-frontend). It serves
server-rendered HTML and delegates authentication/task operations to the
auth and task APIs via HTTP.
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


def load_frontend_public_key(*, testing: bool) -> str:
    """Resolve frontend-service JWT public key for the selected environment."""
    if testing and _has_key_source("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH"):
        return _load_key("TEST_JWT_PUBLIC_KEY", "TEST_JWT_PUBLIC_KEY_PATH")
    return _load_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH")


class Config:
    """Base configuration for all frontend environments."""

    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "frontend-service-dev-secret-change-in-production"
    )

    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))

    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5010")
    TASK_SERVICE_URL: str = os.environ.get("TASK_SERVICE_URL", "http://localhost:5020")
    AUTH_SERVICE_TIMEOUT: int = int(os.environ.get("AUTH_SERVICE_TIMEOUT", "5"))
    TASK_SERVICE_TIMEOUT: int = int(os.environ.get("TASK_SERVICE_TIMEOUT", "5"))
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE: bool = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower() == "true"
    )


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """Configuration for automated tests."""

    DEBUG: bool = True
    TESTING: bool = True

    AUTH_SERVICE_URL: str = os.environ.get("TEST_AUTH_SERVICE_URL", "http://auth-service")
    TASK_SERVICE_URL: str = os.environ.get("TEST_TASK_SERVICE_URL", "http://task-service")
    AUTH_SERVICE_TIMEOUT: int = int(os.environ.get("TEST_AUTH_SERVICE_TIMEOUT", "1"))
    TASK_SERVICE_TIMEOUT: int = int(os.environ.get("TEST_TASK_SERVICE_TIMEOUT", "1"))
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(Config):
    """Configuration for production deployments."""

    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = (
        os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower() == "true"
    )


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
        env: Environment name. When None, falls back to FLASK_ENV.

    Returns:
        The selected configuration class.
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
