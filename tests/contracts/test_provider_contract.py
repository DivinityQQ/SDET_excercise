"""
Provider-side contract tests for the Task Manager API.

Why this file exists:
- Integration tests verify behavior with targeted assertions.
- Contract tests verify payloads against one shared contract file.

These tests intentionally keep helpers small and explicit for learning.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

# Step 4 adds these dependencies to requirements.txt.
# We skip the contract suite gracefully until dependencies are installed.
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
    """Return the OpenAPI contract file path."""
    return Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"


@lru_cache(maxsize=1)
def _load_openapi_spec() -> dict[str, Any]:
    """Load the raw OpenAPI document from disk."""
    with _contract_path().open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


@lru_cache(maxsize=1)
def _load_jsonschema_ready_spec() -> dict[str, Any]:
    """
    Return a JSON-schema-friendly copy of the OpenAPI spec.

    OpenAPI 3.0 uses `nullable: true`, while jsonschema expects an explicit
    `null` type (or `anyOf`). This helper adapts only what we need for tests.
    """
    spec_copy = copy.deepcopy(_load_openapi_spec())
    _convert_nullable_fields_in_place(spec_copy)
    return spec_copy


def _convert_nullable_fields_in_place(node: Any) -> None:
    """
    Recursively convert OpenAPI `nullable` into jsonschema-compatible forms.

    Rules used:
    - `type: X` + `nullable: true` becomes `type: [X, "null"]`.
    - `$ref` + `nullable: true` becomes `anyOf: [{$ref: ...}, {type: "null"}]`.
    """
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
    """Extract the JSON response schema for an endpoint/status pair."""
    operation = openapi_spec["paths"][path_template][method.lower()]
    response = operation["responses"][str(status_code)]
    application_json = response["content"]["application/json"]
    return application_json["schema"]


def _assert_payload_matches_response_schema(
    *,
    payload: dict[str, Any],
    path_template: str,
    method: str,
    status_code: int,
) -> None:
    """
    Validate payload against contract and provide readable error context.

    The assertion message includes endpoint + schema details so failures are
    easier to diagnose than raw jsonschema output alone.
    """
    openapi_spec = _load_openapi_spec()
    validation_spec = _load_jsonschema_ready_spec()

    response_schema = _response_schema_for(
        openapi_spec=openapi_spec,
        path_template=path_template,
        method=method,
        status_code=status_code,
    )

    # Build a root schema so local refs like `#/components/schemas/Task`
    # can resolve during jsonschema validation.
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


class TestOpenApiContractFile:
    """Sanity checks for the OpenAPI contract document."""

    def test_openapi_document_is_valid(self) -> None:
        """
        Verify OpenAPI document structure is valid.

        This catches contract typos early (missing keys, invalid response blocks,
        malformed schema references, and similar structural issues).
        """
        # Arrange
        openapi_spec = _load_openapi_spec()

        # Act / Assert
        openapi_spec_validator.validate(openapi_spec)


class TestProviderResponsesMatchContract:
    """Provider response payload checks against OpenAPI schemas."""

    def test_health_response_matches_contract(
        self,
        client,
        db_session,
    ) -> None:
        """Validate `GET /api/health` response payload contract."""
        # Arrange
        endpoint = "/api/health"

        # Act
        response = client.get(endpoint)

        # Assert
        assert response.status_code == 200
        payload = response.get_json()
        _assert_payload_matches_response_schema(
            payload=payload,
            path_template="/api/health",
            method="get",
            status_code=200,
        )

    def test_create_task_response_matches_contract(
        self,
        client,
        db_session,
        valid_task_data,
        api_headers,
    ) -> None:
        """Validate `POST /api/tasks` success payload contract."""
        # Arrange
        endpoint = "/api/tasks"

        # Act
        response = client.post(
            endpoint,
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )

        # Assert
        assert response.status_code == 201
        payload = response.get_json()
        _assert_payload_matches_response_schema(
            payload=payload,
            path_template="/api/tasks",
            method="post",
            status_code=201,
        )

    def test_get_tasks_response_matches_contract(
        self,
        client,
        db_session,
        valid_task_data,
        api_headers,
    ) -> None:
        """Validate `GET /api/tasks` list payload contract."""
        # Arrange
        create_response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )
        assert create_response.status_code == 201

        # Act
        response = client.get("/api/tasks")

        # Assert
        assert response.status_code == 200
        payload = response.get_json()
        _assert_payload_matches_response_schema(
            payload=payload,
            path_template="/api/tasks",
            method="get",
            status_code=200,
        )

    def test_not_found_error_response_matches_contract(
        self,
        client,
        db_session,
    ) -> None:
        """Validate 404 error payload contract for `GET /api/tasks/{task_id}`."""
        # Arrange
        missing_task_id = 999_999

        # Act
        response = client.get(f"/api/tasks/{missing_task_id}")

        # Assert
        assert response.status_code == 404
        payload = response.get_json()
        _assert_payload_matches_response_schema(
            payload=payload,
            path_template="/api/tasks/{task_id}",
            method="get",
            status_code=404,
        )
