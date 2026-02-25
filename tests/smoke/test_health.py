"""
Smoke tests for the microservices stack.

Smoke tests are lightweight, fast checks that verify the critical paths
of a deployed system are operational.  They run against a live (or
docker-compose) stack and answer one question: "is the system up and
minimally functional?"

Unlike unit or integration tests, smoke tests do NOT mock anything --
every request travels through the real gateway, auth-service, and
task-service.  If any of these tests fail, the deployment should be
considered broken and deeper test suites should not be attempted.

Key SDET Concepts Demonstrated:
- Smoke testing against a running stack
- Health-endpoint verification per service
- Quick end-to-end critical-path validation (register, login, CRUD)
- Using plain ``requests`` (no browser) for fast HTTP-level checks
"""

import time
import pytest
import requests

pytestmark = pytest.mark.smoke


def test_gateway_root_is_running(smoke_base_url):
    """Test that the gateway root URL responds with 200 OK."""
    # Arrange -- nothing to set up; smoke_base_url fixture provides the gateway URL

    # Act
    response = requests.get(f"{smoke_base_url}/", timeout=5)

    # Assert
    assert response.status_code == 200


def test_gateway_health(smoke_base_url):
    """Test that the gateway health endpoint reports itself healthy."""
    # Arrange -- nothing to set up

    # Act
    response = requests.get(f"{smoke_base_url}/api/health", timeout=5)

    # Assert
    assert response.status_code == 200
    assert response.json().get("service") == "gateway"


def test_auth_service_health_via_gateway(smoke_base_url):
    """Test that the auth-service health endpoint is reachable through the gateway."""
    # Arrange -- nothing to set up

    # Act
    response = requests.get(f"{smoke_base_url}/api/auth/health", timeout=5)

    # Assert
    assert response.status_code == 200
    assert response.json().get("service") == "auth"


def test_full_smoke_register_login_and_task_flow(smoke_base_url):
    """Test the critical path: register, login, create task, read it, delete it."""
    # Arrange -- generate unique credentials to avoid collisions across runs
    run_id = int(time.time() * 1000)
    username = f"smoke_{run_id}"
    email = f"smoke_{run_id}@example.com"
    password = "SmokePass123!"

    # Act & Assert -- each step validates before proceeding to the next
    # ===== REGISTER =====
    register_response = requests.post(
        f"{smoke_base_url}/api/auth/register",
        json={"username": username, "email": email, "password": password},
        timeout=5,
    )
    assert register_response.status_code == 201

    # ===== LOGIN =====
    login_response = requests.post(
        f"{smoke_base_url}/api/auth/login",
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

    # ===== CREATE TASK =====
    create_response = requests.post(
        f"{smoke_base_url}/api/tasks",
        json={"title": "Smoke task"},
        headers=headers,
        timeout=5,
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    # ===== READ TASK =====
    get_response = requests.get(
        f"{smoke_base_url}/api/tasks/{task_id}", headers=headers, timeout=5
    )
    assert get_response.status_code == 200

    # ===== DELETE TASK =====
    delete_response = requests.delete(
        f"{smoke_base_url}/api/tasks/{task_id}", headers=headers, timeout=5
    )
    assert delete_response.status_code == 200
