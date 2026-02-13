"""
Shared pytest fixtures for gateway service tests.

Provides the reusable test infrastructure (Flask app and HTTP client)
needed by unit and integration test suites in the gateway service.
The gateway acts as a reverse proxy, so its fixtures are intentionally
lightweight -- no database or factory fixtures are needed because the
gateway itself holds no persistent state.

Key SDET Concepts Demonstrated:
- Fixture scoping (session vs. function) for performance and isolation
- Environment variable overrides to inject deterministic service URLs
- Isolating the system-under-test (gateway) from real downstream services
"""

from __future__ import annotations

import os

import pytest

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_AUTH_SERVICE_URL"] = "http://auth-service.test"
os.environ["TEST_TASK_SERVICE_URL"] = "http://task-service.test"
os.environ["TEST_FRONTEND_SERVICE_URL"] = "http://frontend.test"
os.environ["TEST_PROXY_TIMEOUT"] = "1"

from gateway_app import create_app


@pytest.fixture(scope="session")
def app():
    """
    Provide the Flask application instance for the entire test session.

    Creates the gateway app once with the 'testing' config and reuses
    it across all tests to avoid repeated startup overhead.
    """
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """
    Provide a Flask test client scoped to a single test function.

    Opens a new test-client context for every test so that request
    state (cookies, headers) never leaks between tests.
    """
    with app.test_client() as test_client:
        yield test_client
