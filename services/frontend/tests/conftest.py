"""
Shared pytest fixtures for frontend-service tests.

Provides the reusable test infrastructure (Flask app and HTTP client)
needed by integration and contract test suites in this service.  Because
the frontend BFF is stateless (no database), the fixture set is lighter
than those of the auth and task services.

Key SDET Concepts Demonstrated:
- Fixture scoping (session vs. function) for performance and isolation
- Environment variable overrides for deterministic test configuration
- Shared JWT test keys for cross-service token verification
"""

from __future__ import annotations

import os

import pytest

from shared.test_helpers import TEST_PUBLIC_KEY

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_JWT_PUBLIC_KEY"] = TEST_PUBLIC_KEY

from frontend_app import create_app


@pytest.fixture(scope="session")
def app():
    """
    Provide the Flask application instance for the entire test session.

    Creates the app once with the 'testing' config and reuses it
    across all tests to avoid repeated startup overhead.
    """
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """
    Provide a Flask test client scoped to a single test function.

    Opens a new test-client context for every test so that request
    state (cookies, sessions) never leaks between tests.
    """
    with app.test_client() as test_client:
        yield test_client
