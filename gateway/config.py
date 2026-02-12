"""
Gateway Service — Configuration.

Defines environment-specific configuration classes for the API gateway.
Each class captures the URLs of the downstream microservices that the
gateway proxies to, as well as operational settings such as request
timeouts.  The ``get_config`` factory selects the right class based on
the ``FLASK_ENV`` environment variable (or an explicit key).

Key Concepts Demonstrated:
- Class-based configuration with inheritance for DRY defaults
- Environment-variable overrides for 12-factor app deployability
- Separate testing configuration with short timeouts and fake URLs
"""

from __future__ import annotations

import os


class Config:
    """
    Base (shared) configuration for the gateway.

    All environment-specific classes inherit from ``Config`` so that
    common defaults only need to be stated once.  Individual settings
    can be overridden by environment variables, following 12-factor
    app conventions.
    """

    # URL of the authentication microservice.  In production this is the
    # cluster-internal DNS name; locally it can be overridden via env var.
    AUTH_SERVICE_URL: str = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5000")

    # URL of the task-management microservice (also serves the web UI).
    TASK_SERVICE_URL: str = os.environ.get("TASK_SERVICE_URL", "http://task-service:5000")

    # Maximum seconds the gateway will wait for a downstream response
    # before returning 502 Bad Gateway.  Kept deliberately short to
    # avoid tying up gateway workers when a backend is unhealthy.
    PROXY_TIMEOUT: int = int(os.environ.get("PROXY_TIMEOUT", "10"))


class DevelopmentConfig(Config):
    """
    Development-oriented overrides.

    Enables Flask debug mode for auto-reload and richer error pages
    while retaining the default service URLs from ``Config``.
    """

    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """
    Test-suite overrides.

    Points service URLs at non-routable test hosts so that unit tests
    never accidentally hit real services.  The timeout is reduced to
    1 second so tests that simulate timeouts complete quickly.
    """

    DEBUG: bool = True
    TESTING: bool = True
    # Non-routable hostnames ensure tests never leak real HTTP requests.
    AUTH_SERVICE_URL: str = os.environ.get("TEST_AUTH_SERVICE_URL", "http://auth.test")
    TASK_SERVICE_URL: str = os.environ.get("TEST_TASK_SERVICE_URL", "http://tasks.test")
    # Aggressive timeout keeps test runs fast when simulating slow backends.
    PROXY_TIMEOUT: int = int(os.environ.get("TEST_PROXY_TIMEOUT", "1"))


class ProductionConfig(Config):
    """
    Production-hardened overrides.

    Disables debug mode and testing flags.  All other values are
    expected to come from environment variables set by the deployment
    orchestrator (Docker Compose, Kubernetes, etc.).
    """

    DEBUG: bool = False
    TESTING: bool = False


# Lookup table mapping environment name strings to their config classes.
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    """
    Return the configuration class for the given environment.

    Args:
        env: One of ``"development"``, ``"testing"``, or
            ``"production"``.  When *None*, the ``FLASK_ENV``
            environment variable is consulted, falling back to
            ``"development"`` if unset.

    Returns:
        The ``Config`` subclass matching the requested environment,
        or ``DevelopmentConfig`` if the key is unrecognised.
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
