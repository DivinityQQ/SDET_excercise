"""
Provider-side contract tests for the task service.

Loads the shared OpenAPI specification (tasks_openapi.yaml) and validates
that real HTTP responses from the running task-service match the documented
response schemas. Also verifies that the OpenAPI document itself is
structurally valid.

Key SDET Concepts Demonstrated:
- Provider-side contract testing (service proves it honours the contract)
- OpenAPI / JSON-Schema validation with jsonschema + openapi-spec-validator
- Schema-adaptation layer for OpenAPI 3.0 nullable -> JSON-Schema anyOf
- Caching parsed specs with @lru_cache for performance
- Shared contract file as a single source of truth across services
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml", reason="Install pyyaml for contract tests.")
jsonschema = pytest.importorskip(
    "jsonschema", reason="Install jsonschema for contract tests."
)
openapi_spec_validator = pytest.importorskip(
    "openapi_spec_validator",
    reason="Install openapi-spec-validator for contract tests.",
)

pytestmark = pytest.mark.contract


def _contract_path() -> Path:
    """Return the absolute path to the shared OpenAPI contract YAML file."""
    return Path(__file__).resolve().parents[4] / "contracts" / "tasks_openapi.yaml"


@lru_cache(maxsize=1)
def _load_openapi_spec() -> dict[str, Any]:
    """Load and cache the raw OpenAPI spec from disk."""
    with _contract_path().open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


@lru_cache(maxsize=1)
def _load_jsonschema_ready_spec() -> dict[str, Any]:
    """
    Load the spec and convert OpenAPI 3.0 'nullable' fields to JSON-Schema-compatible form.

    OpenAPI 3.0 uses ``nullable: true`` which is not natively understood by
    JSON-Schema validators, so this helper rewrites those nodes into
    ``anyOf`` / type-array representations.
    """
    spec_copy = copy.deepcopy(_load_openapi_spec())
    _convert_nullable_fields_in_place(spec_copy)
    return spec_copy


def _convert_nullable_fields_in_place(node: Any) -> None:
    """Recursively rewrite OpenAPI 3.0 nullable nodes into JSON-Schema unions."""
    if isinstance(node, dict):
        for value in list(node.values()):
            _convert_nullable_fields_in_place(value)

        if node.get("nullable") is True:
            node.pop("nullable", None)

            if "type" in node:
                node_type = node["type"]
                if isinstance(node_type, list):
                    if "null" not in node_type:
                        node_type.append("null")
                else:
                    node["type"] = [node_type, "null"]
            elif "$ref" in node:
                ref_value = node.pop("$ref")
                remaining_fields = dict(node)
                node.clear()
                node.update(remaining_fields)
                node["anyOf"] = [{"$ref": ref_value}, {"type": "null"}]
            else:
                node["anyOf"] = [{"type": "null"}]

    elif isinstance(node, list):
        for item in node:
            _convert_nullable_fields_in_place(item)


def _response_schema_for(
    openapi_spec: dict[str, Any],
    path_template: str,
    method: str,
    status_code: int,
) -> dict[str, Any]:
    """Extract the response JSON-schema for a given path/method/status from the spec."""
    operation = openapi_spec["paths"][path_template][method.lower()]
    response = operation["responses"][str(status_code)]
    return response["content"]["application/json"]["schema"]


def _assert_payload_matches_response_schema(
    *,
    payload: dict[str, Any],
    path_template: str,
    method: str,
    status_code: int,
) -> None:
    """
    Validate a response payload against the contract schema.

    Loads both the raw and JSON-Schema-ready specs, locates the expected
    schema by path/method/status, injects shared component definitions,
    then runs JSON-Schema validation. On failure, raises an AssertionError
    with a detailed diagnostic message.
    """
    openapi_spec = _load_openapi_spec()
    validation_spec = _load_jsonschema_ready_spec()
    response_schema = _response_schema_for(
        openapi_spec=openapi_spec,
        path_template=path_template,
        method=method,
        status_code=status_code,
    )

    validation_schema = copy.deepcopy(response_schema)
    validation_schema["components"] = validation_spec["components"]

    try:
        jsonschema.validate(
            instance=payload,
            schema=validation_schema,
            format_checker=jsonschema.FormatChecker(),
        )
    except jsonschema.ValidationError as exc:
        compact_payload = json.dumps(payload, indent=2, sort_keys=True)
        raise AssertionError(
            "Contract validation failed.\n"
            f"Endpoint: {method.upper()} {path_template}\n"
            f"Expected response status: {status_code}\n"
            f"Validation path: {'/'.join(str(part) for part in exc.path) or '<root>'}\n"
            f"Message: {exc.message}\n"
            f"Payload:\n{compact_payload}"
        ) from exc


class TestTaskOpenApiContractFile:
    """Tests that validate the OpenAPI contract document itself."""

    def test_openapi_document_is_valid(self) -> None:
        """Test that the tasks_openapi.yaml file passes OpenAPI structural validation."""
        # Arrange - provided by _load_openapi_spec()

        # Act & Assert
        openapi_spec_validator.validate(_load_openapi_spec())


class TestTaskProviderResponsesMatchContract:
    """Tests that verify live task-service responses match the OpenAPI contract schemas."""

    def test_health_response_matches_contract(self, client, db_session):
        """Test that GET /api/health returns a payload conforming to the contract."""
        # Arrange - provided by db_session (app context)

        # Act
        response = client.get("/api/health")

        # Assert
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/health",
            method="get",
            status_code=200,
        )

    def test_create_task_response_matches_contract(
        self, client, db_session, valid_task_data, api_headers
    ):
        """Test that POST /api/tasks 201 response conforms to the contract."""
        # Arrange - provided by valid_task_data and api_headers fixtures

        # Act
        response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/tasks",
            method="post",
            status_code=201,
        )

    def test_get_tasks_response_matches_contract(
        self, client, db_session, valid_task_data, api_headers
    ):
        """Test that GET /api/tasks 200 response conforms to the contract."""
        # Arrange — create a task so the list is non-empty
        create_response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )
        assert create_response.status_code == 201

        # Act
        response = client.get("/api/tasks", headers=api_headers)

        # Assert
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/tasks",
            method="get",
            status_code=200,
        )

    def test_unauthorized_error_response_matches_contract(self, client, db_session):
        """Test that an unauthenticated request returns a 401 body matching the contract."""
        # Arrange - no auth headers provided

        # Act
        response = client.get("/api/tasks")

        # Assert
        assert response.status_code == 401
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/tasks",
            method="get",
            status_code=401,
        )
