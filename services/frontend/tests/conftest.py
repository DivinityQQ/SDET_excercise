"""
Shared pytest fixtures for frontend-service tests.
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
    """Provide frontend app instance."""
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    """Provide test client per test function."""
    with app.test_client() as test_client:
        yield test_client
