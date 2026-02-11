"""Configuration for gateway service."""

from __future__ import annotations

import os


class Config:
    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5000")
    TASK_SERVICE_URL: str = os.environ.get("TASK_SERVICE_URL", "http://task-service:5000")
    PROXY_TIMEOUT: int = int(os.environ.get("PROXY_TIMEOUT", "10"))


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    DEBUG: bool = True
    TESTING: bool = True
    AUTH_SERVICE_URL: str = os.environ.get("TEST_AUTH_SERVICE_URL", "http://auth.test")
    TASK_SERVICE_URL: str = os.environ.get("TEST_TASK_SERVICE_URL", "http://tasks.test")
    PROXY_TIMEOUT: int = int(os.environ.get("TEST_PROXY_TIMEOUT", "1"))


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

