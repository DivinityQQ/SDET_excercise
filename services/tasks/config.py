"""Configuration for task service."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "task-service-dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'tasks.db'}",
    )

    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "dev-jwt-secret-change-in-production"
    )
    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))

    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5010")
    AUTH_SERVICE_TIMEOUT: int = int(os.environ.get("AUTH_SERVICE_TIMEOUT", "5"))


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
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
    DEBUG: bool = False
    TESTING: bool = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])

