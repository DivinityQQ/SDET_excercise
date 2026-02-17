"""
Consumer-side contract tests for the frontend BFF service.

Validates that the assumptions hard-coded into the frontend route handlers
(expected status codes, response field names, enum values) still align with
the shared OpenAPI contract files in ``contracts/``.  This is a form of
*consumer-side* contract testing: the tests do **not** call live services;
instead they parse the YAML specs and assert structural invariants that the
frontend code relies on.

If a contract file is updated in a way that breaks the frontend's
expectations (e.g. renaming ``token`` to ``access_token``), these tests will
catch the incompatibility before any integration or E2E test runs.

Key SDET Concepts Demonstrated:
- Consumer-driven contract testing against OpenAPI specifications
- ``$ref`` resolution for navigating nested schemas
- Enum synchronisation checks between duplicated types
- ``pytest.importorskip`` for optional-dependency gating
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from services.frontend.frontend_app.models import TaskPriority, TaskStatus

yaml = pytest.importorskip("yaml", reason="Install pyyaml for contract tests.")

pytestmark = pytest.mark.contract


def _contracts_dir() -> Path:
    """
    Return the absolute path to the shared contracts directory.

    Navigates up from this test file's location to the repository root
    and appends ``contracts/``.
    """
    return Path(__file__).resolve().parents[4] / "contracts"


@lru_cache(maxsize=2)
def _load_openapi_spec(filename: str) -> dict[str, Any]:
    """
    Load and cache an OpenAPI YAML document from contracts/.

    Uses ``lru_cache`` so each spec file is read only once per test
    session, regardless of how many tests reference it.

    Args:
        filename: Name of the YAML file inside the contracts directory
            (e.g. ``"auth_openapi.yaml"``).

    Returns:
        The parsed OpenAPI specification as a nested dictionary.
    """
    with (_contracts_dir() / filename).open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


def _response_schema_for(
    openapi_spec: dict[str, Any], path_template: str, method: str, status_code: int
) -> dict[str, Any]:
    """
    Extract the JSON response schema for a given path, method, and status code.

    Navigates the OpenAPI ``paths`` tree to locate the correct ``content ->
    application/json -> schema`` block for the specified operation/response.

    Args:
        openapi_spec: The parsed OpenAPI specification dictionary.
        path_template: OpenAPI path template (e.g. ``"/api/auth/login"``).
        method: HTTP method in lowercase (e.g. ``"post"``).
        status_code: HTTP status code as an integer (e.g. ``200``).

    Returns:
        The schema dictionary for the matched response.
    """
    operation = openapi_spec["paths"][path_template][method.lower()]
    response = operation["responses"][str(status_code)]
    return response["content"]["application/json"]["schema"]


def _resolve_schema_ref(openapi_spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve local ``$ref`` references in OpenAPI schemas.

    Walks ``#/``-prefixed JSON Pointer references to return the
    referenced schema object.  Only supports local references, which is
    sufficient for this repository.

    Args:
        openapi_spec: The parsed OpenAPI specification dictionary.
        schema: A schema dict that may contain a ``$ref`` key.

    Returns:
        The resolved schema dictionary (or *schema* unchanged if no
        ``$ref`` is present).

    Raises:
        AssertionError: If the reference is non-local or resolves to a
            non-dict node.
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
    Test that the auth login contract preserves the fields and statuses
    the frontend relies on.

    The frontend's ``login_submit`` handler expects a 200 response with a
    required ``token`` field, and renders a specific error message for 401
    responses.  This test reads the shared OpenAPI spec and confirms those
    expectations still hold.
    """
    # Arrange
    auth_spec = _load_openapi_spec("auth_openapi.yaml")

    # Act
    responses = auth_spec["paths"]["/api/auth/login"]["post"]["responses"]
    success_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/login", "post", 200),
    )
    unauthorized_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/login", "post", 401),
    )

    # Assert
    assert {"200", "401"}.issubset(responses.keys())
    assert "token" in success_schema.get("required", [])
    assert "error" in unauthorized_schema.get("required", [])


def test_auth_register_response_contract_matches_frontend_expectations():
    """
    Test that the auth register contract preserves the statuses the
    frontend handles.

    The frontend's ``register_submit`` handler expects a 201 on success
    and renders error messages extracted from 400 / 409 responses.  This
    test verifies those status codes and the ``error`` field are still
    present in the spec.
    """
    # Arrange
    auth_spec = _load_openapi_spec("auth_openapi.yaml")

    # Act
    responses = auth_spec["paths"]["/api/auth/register"]["post"]["responses"]
    bad_request_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/register", "post", 400),
    )
    conflict_schema = _resolve_schema_ref(
        auth_spec,
        _response_schema_for(auth_spec, "/api/auth/register", "post", 409),
    )

    # Assert
    assert {"201", "400", "409"}.issubset(responses.keys())
    assert "error" in bad_request_schema.get("required", [])
    assert "error" in conflict_schema.get("required", [])


def test_task_endpoint_status_codes_match_frontend_handling():
    """
    Test that task endpoints expose every status code the frontend
    routes explicitly handle.

    Each frontend route handler contains ``if response.status_code ==``
    branches for specific codes.  This test ensures the task API spec
    still declares those codes, catching silent removals before they
    reach integration testing.
    """
    # Arrange
    task_spec = _load_openapi_spec("tasks_openapi.yaml")

    expected_responses = {
        ("/api/tasks", "get"): {"200", "401"},
        ("/api/tasks", "post"): {"201", "400", "401"},
        ("/api/tasks/{task_id}", "get"): {"200", "401", "404"},
        ("/api/tasks/{task_id}", "put"): {"200", "400", "401", "404"},
        ("/api/tasks/{task_id}", "delete"): {"200", "401", "404"},
        ("/api/tasks/{task_id}/status", "patch"): {"200", "400", "401", "404"},
    }

    # Act & Assert
    for (path_template, method), required_statuses in expected_responses.items():
        responses = task_spec["paths"][path_template][method]["responses"]
        assert required_statuses.issubset(responses.keys())


def test_task_payload_shape_matches_frontend_template_requirements():
    """
    Test that the task response schema includes every field used by
    frontend Jinja templates and view helpers.

    The ``_deserialize_task`` helper and the templates depend on
    ``due_date``, ``created_at``, and ``updated_at`` being ISO-8601
    date-time strings (or nullable).  This test confirms those fields
    are still declared with the correct types and formats in the spec.
    """
    # Arrange
    task_spec = _load_openapi_spec("tasks_openapi.yaml")

    # Act
    task_schema = _resolve_schema_ref(
        task_spec,
        task_spec["components"]["schemas"]["Task"],
    )

    required = set(task_schema["required"])

    due_date = task_schema["properties"]["due_date"]
    created_at = task_schema["properties"]["created_at"]
    updated_at = task_schema["properties"]["updated_at"]

    # Assert
    assert {
        "id",
        "title",
        "status",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
    }.issubset(required)
    assert due_date["type"] == "string"
    assert due_date["format"] == "date-time"
    assert due_date.get("nullable") is True

    assert created_at["type"] == "string" and created_at["format"] == "date-time"
    assert updated_at["type"] == "string" and updated_at["format"] == "date-time"


def test_frontend_enums_match_task_openapi_contract():
    """
    Test that the duplicated frontend enums stay in sync with the task
    API contract enums.

    ``TaskStatus`` and ``TaskPriority`` are intentionally duplicated in
    the frontend service for deployment independence.  This test reads
    the canonical enum values from the OpenAPI spec and asserts that the
    frontend copies match, catching drift before it causes runtime
    mismatches.
    """
    # Arrange
    task_spec = _load_openapi_spec("tasks_openapi.yaml")

    # Act
    contract_statuses = task_spec["components"]["schemas"]["TaskStatus"]["enum"]
    contract_priorities = task_spec["components"]["schemas"]["TaskPriority"]["enum"]

    frontend_statuses = [status.value for status in TaskStatus]
    frontend_priorities = [priority.value for priority in TaskPriority]

    # Assert
    assert sorted(frontend_statuses) == sorted(contract_statuses)
    assert sorted(frontend_priorities) == sorted(contract_priorities)
