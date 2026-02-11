"""Shared fixtures for gateway tests."""

from __future__ import annotations

import os

import pytest

os.environ["FLASK_ENV"] = "testing"
os.environ["TEST_AUTH_SERVICE_URL"] = "http://auth-service.test"
os.environ["TEST_TASK_SERVICE_URL"] = "http://task-service.test"
os.environ["TEST_PROXY_TIMEOUT"] = "1"

from gateway_app import create_app


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    yield application


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as test_client:
        yield test_client

