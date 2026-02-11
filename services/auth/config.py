"""Configuration for auth service."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "auth-service-dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'auth.db'}",
    )

    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "dev-jwt-secret-change-in-production"
    )
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    JWT_CLOCK_SKEW_SECONDS: int = int(os.environ.get("JWT_CLOCK_SKEW_SECONDS", "30"))


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    DEBUG: bool = True
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'test_auth.db'}?check_same_thread=False",
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"pool_pre_ping": True}
    JWT_SECRET_KEY: str = os.environ.get(
        "TEST_JWT_SECRET_KEY", "test-jwt-secret-key-for-local-tests-123456"
    )
    JWT_EXPIRY_HOURS: int = int(os.environ.get("TEST_JWT_EXPIRY_HOURS", "1"))


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

