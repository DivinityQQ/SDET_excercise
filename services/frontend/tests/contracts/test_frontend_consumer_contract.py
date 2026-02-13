"""
Consumer-side contract tests for the frontend BFF service.

These tests verify that frontend assumptions about auth/task APIs still match
the shared OpenAPI contracts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from frontend_app.models import TaskPriority, TaskStatus

yaml = pytest.importorskip("yaml", reason="Install pyyaml for contract tests.")

pytestmark = pytest.mark.contract


def _contracts_dir() -> Path:
    """Return absolute path to the shared contracts directory."""
    return Path(__file__).resolve().parents[4] / "contracts"


@lru_cache(maxsize=2)
def _load_openapi_spec(filename: str) -> dict[str, Any]:
    """Load and cache an OpenAPI YAML document from contracts/."""
    with (_contracts_dir() / filename).open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


def _response_schema_for(
    openapi_spec: dict[str, Any], path_template: str, method: str, status_code: int
) -> dict[str, Any]:
    """Extract response schema for path/method/status from an OpenAPI spec."""
    operation = openapi_spec["paths"][path_template][method.lower()]
    response = operation["responses"][str(status_code)]
    return response["content"]["application/json"]["schema"]


def _resolve_schema_ref(openapi_spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve local ``$ref`` references in OpenAPI schemas.

    Only supports local references (``#/...``), which is sufficient for this repo.
    """
    if "$ref" not in schema:
        return schema

    ref = schema["$ref"]
    if not ref.startswith("#/"):
        raise AssertionError(f"Unexpected non-local schema reference: {ref}")

    node: Any = openapi_spec
    for part in ref[2:].split("/"):
        node = node[part]

    if not isinstance(node, dict):
        raise AssertionError(f"Resolved schema for ref {ref} is not an object")
    return node


def test_auth_login_response_contract_matches_frontend_expectations():
    """
    Ensure auth login contract preserves fields/statuses the frontend uses.

    Frontend requirements:
    - success status 200 with required ``token`` field
    - invalid credentials status 401 with ``error`` field
    """
    auth_spec = _load_openapi_spec("auth_openapi.yaml")

    responses = auth_spec["paths"]["/api/auth/login"]["post"]["responses"]
    assert {"200", "401"}.issubset(responses.keys())

    success_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/login", "post", 200),
    )
    assert "token" in success_schema.get("required", [])

    unauthorized_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/login", "post", 401),
    )
    assert "error" in unauthorized_schema.get("required", [])


def test_auth_register_response_contract_matches_frontend_expectations():
    """
    Ensure auth register contract preserves frontend-handled statuses.

    Frontend requirements:
    - success status 201
    - validation/duplicate status 400 or 409 with ``error`` field
    """
    auth_spec = _load_openapi_spec("auth_openapi.yaml")
    responses = auth_spec["paths"]["/api/auth/register"]["post"]["responses"]
    assert {"201", "400", "409"}.issubset(responses.keys())

    bad_request_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/register", "post", 400),
    )
    conflict_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/register", "post", 409),
    )
    assert "error" in bad_request_schema.get("required", [])
    assert "error" in conflict_schema.get("required", [])


def test_task_endpoint_status_codes_match_frontend_handling():
    """Ensure task endpoints expose statuses frontend routes explicitly handle."""
    task_spec = _load_openapi_spec("tasks_openapi.yaml")

    expected_responses = {
        ("/api/tasks", "get"): {"200", "401"},
        ("/api/tasks", "post"): {"201", "400", "401"},
        ("/api/tasks/{task_id}", "get"): {"200", "401", "404"},
        ("/api/tasks/{task_id}", "put"): {"200", "400", "401", "404"},
        ("/api/tasks/{task_id}", "delete"): {"200", "401", "404"},
        ("/api/tasks/{task_id}/status", "patch"): {"200", "400", "401", "404"},
    }

    for (path_template, method), required_statuses in expected_responses.items():
        responses = task_spec["paths"][path_template][method]["responses"]
        assert required_statuses.issubset(responses.keys())


def test_task_payload_shape_matches_frontend_template_requirements():
    """
    Ensure task response schema includes fields used by frontend templates/views.

    Frontend templates require ``strftime``-compatible datetime fields and
    string status/priority/title fields.
    """
    task_spec = _load_openapi_spec("tasks_openapi.yaml")
    task_schema = _resolve_schema_ref(
        task_spec,
        task_spec["components"]["schemas"]["Task"],
    )

    required = set(task_schema["required"])
    assert {
        "id",
        "title",
        "status",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
    }.issubset(required)

    due_date = task_schema["properties"]["due_date"]
    assert due_date["type"] == "string"
    assert due_date["format"] == "date-time"
    assert due_date.get("nullable") is True

    created_at = task_schema["properties"]["created_at"]
    updated_at = task_schema["properties"]["updated_at"]
    assert created_at["type"] == "string" and created_at["format"] == "date-time"
    assert updated_at["type"] == "string" and updated_at["format"] == "date-time"


def test_frontend_enums_match_task_openapi_contract():
    """Ensure duplicated frontend enums stay in sync with task API contract enums."""
    task_spec = _load_openapi_spec("tasks_openapi.yaml")

    contract_statuses = task_spec["components"]["schemas"]["TaskStatus"]["enum"]
    contract_priorities = task_spec["components"]["schemas"]["TaskPriority"]["enum"]

    frontend_statuses = [status.value for status in TaskStatus]
    frontend_priorities = [priority.value for priority in TaskPriority]

    assert sorted(frontend_statuses) == sorted(contract_statuses)
    assert sorted(frontend_priorities) == sorted(contract_priorities)
