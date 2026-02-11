import os
import time
import pytest
import requests


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:5000")

pytestmark = pytest.mark.smoke


def test_gateway_root_is_running():
    response = requests.get(f"{BASE_URL}/", timeout=5)
    assert response.status_code == 200


def test_gateway_health():
    response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    assert response.status_code == 200
    assert response.json().get("service") == "gateway"


def test_auth_service_health_via_gateway():
    response = requests.get(f"{BASE_URL}/api/auth/health", timeout=5)
    assert response.status_code == 200
    assert response.json().get("service") == "auth"


def test_full_smoke_register_login_and_task_flow():
    run_id = int(time.time() * 1000)
    username = f"smoke_{run_id}"
    email = f"smoke_{run_id}@example.com"
    password = "SmokePass123!"

    register_response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"username": username, "email": email, "password": password},
        timeout=5,
    )
    assert register_response.status_code == 201

    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=5,
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    create_response = requests.post(
        f"{BASE_URL}/api/tasks",
        json={"title": "Smoke task"},
        headers=headers,
        timeout=5,
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    get_response = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers, timeout=5)
    assert get_response.status_code == 200

    delete_response = requests.delete(f"{BASE_URL}/api/tasks/{task_id}", headers=headers, timeout=5)
    assert delete_response.status_code == 200
