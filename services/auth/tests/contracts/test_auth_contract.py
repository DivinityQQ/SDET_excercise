"""
Provider-side contract tests for the auth service.

Validates that every response returned by the auth service API matches
the shapes and types defined in the shared OpenAPI contract file
(contracts/auth_openapi.yaml).  This is a form of *provider-side*
contract testing: the real service is exercised through the Flask test
client, and each response body is validated against the corresponding
JSON Schema derived from the OpenAPI specification.

Key SDET Concepts Demonstrated:
- Contract / schema testing to enforce API compatibility
- Provider-side verification against an OpenAPI specification
- OpenAPI-to-JSON-Schema conversion (nullable field handling)
- Separation of spec-validity checks from behavioural checks
- Reusable helper functions for DRY schema-validation logic
"""

from __future__ import annotations

import copy
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
    """Return the absolute path to the auth OpenAPI contract YAML file."""
    return Path(__file__).resolve().parents[4] / "contracts" / "auth_openapi.yaml"


@lru_cache(maxsize=1)
def _load_openapi_spec() -> dict[str, Any]:
    """
    Load and cache the raw OpenAPI specification from disk.

    Uses ``lru_cache`` so the file is read only once per test session,
    regardless of how many tests reference the spec.
    """
    with _contract_path().open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


@lru_cache(maxsize=1)
def _load_jsonschema_ready_spec() -> dict[str, Any]:
    """
    Load the OpenAPI spec and convert it into a JSON-Schema-compatible form.

    OpenAPI 3.0 uses ``nullable: true`` which is not valid in JSON Schema
    draft-07+.  This helper deep-copies the spec and rewrites those fields
    so that ``jsonschema.validate`` works correctly.
    """
    spec_copy = copy.deepcopy(_load_openapi_spec())
    _convert_nullable_fields_in_place(spec_copy)
    return spec_copy


def _convert_nullable_fields_in_place(node: Any) -> None:
    """
    Recursively rewrite OpenAPI ``nullable`` annotations to JSON Schema form.

    Walks the entire spec tree and converts ``nullable: true`` into either
    a ``type`` array (e.g. ``["string", "null"]``) or an ``anyOf`` union,
    depending on how the original field was defined.
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
    openapi_spec: dict[str, Any], path_template: str, method: str, status_code: int
) -> dict[str, Any]:
    """
    Extract the JSON response schema for a given path, method, and status code.

    Navigates the OpenAPI ``paths`` tree to locate the correct ``content ->
    application/json -> schema`` block for the specified operation/response.
    """
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
    Validate that a response payload conforms to the OpenAPI contract.

    Looks up the expected schema from the spec, attaches shared component
    definitions for ``$ref`` resolution, and runs ``jsonschema.validate``
    with format checking enabled.
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

    jsonschema.validate(
        instance=payload,
        schema=validation_schema,
        format_checker=jsonschema.FormatChecker(),
    )


class TestAuthOpenApiContractFile:
    """Tests that the OpenAPI contract document itself is structurally valid."""

    def test_openapi_document_is_valid(self) -> None:
        """Test that the auth OpenAPI YAML passes formal spec validation."""
        # Arrange
        spec = _load_openapi_spec()

        # Act & Assert
        openapi_spec_validator.validate(spec)


class TestAuthProviderResponsesMatchContract:
    """Tests that live auth service responses conform to the OpenAPI contract."""

    def test_health_response_matches_contract(self, client, db_session):
        """Test that GET /health returns a body matching the contract schema."""
        # Arrange - (no setup needed)

        # Act
        response = client.get("/api/auth/health")

        # Assert
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/health",
            method="get",
            status_code=200,
        )

    def test_register_response_matches_contract(self, client, db_session):
        """Test that POST /register returns a body matching the contract schema."""
        # Arrange
        registration_data = {
            "username": "contract_user",
            "email": "contract_user@example.com",
            "password": "StrongPass123!",
        }

        # Act
        response = client.post(
            "/api/auth/register",
            json=registration_data,
        )

        # Assert
        assert response.status_code == 201
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/register",
            method="post",
            status_code=201,
        )

    def test_login_response_matches_contract(self, client, db_session, user_factory):
        """Test that POST /login returns a body matching the contract schema."""
        # Arrange
        user_factory(
            username="contract_login",
            email="contract_login@example.com",
            password="StrongPass123!",
        )

        # Act
        response = client.post(
            "/api/auth/login",
            json={"username": "contract_login", "password": "StrongPass123!"},
        )

        # Assert
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/login",
            method="post",
            status_code=200,
        )

    def test_verify_error_response_matches_contract(self, client, db_session):
        """Test that GET /verify without auth returns an error matching the contract schema."""
        # Arrange - (no setup needed)

        # Act
        response = client.get("/api/auth/verify")

        # Assert
        assert response.status_code == 401
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/verify",
            method="get",
            status_code=401,
        )
