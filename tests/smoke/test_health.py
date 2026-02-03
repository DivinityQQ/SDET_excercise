import os
import pytest
import requests


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:5000")

pytestmark = pytest.mark.smoke


def test_app_is_running():
    response = requests.get(f"{BASE_URL}/", timeout=5)
    assert response.status_code == 200


def test_api_health():
    response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    assert response.status_code == 200
