"""Provider-side contract tests for auth service."""

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
    return Path(__file__).resolve().parents[4] / "contracts" / "auth_openapi.yaml"


@lru_cache(maxsize=1)
def _load_openapi_spec() -> dict[str, Any]:
    with _contract_path().open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


@lru_cache(maxsize=1)
def _load_jsonschema_ready_spec() -> dict[str, Any]:
    spec_copy = copy.deepcopy(_load_openapi_spec())
    _convert_nullable_fields_in_place(spec_copy)
    return spec_copy


def _convert_nullable_fields_in_place(node: Any) -> None:
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
    def test_openapi_document_is_valid(self) -> None:
        openapi_spec_validator.validate(_load_openapi_spec())


class TestAuthProviderResponsesMatchContract:
    def test_health_response_matches_contract(self, client, db_session):
        response = client.get("/api/auth/health")
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/health",
            method="get",
            status_code=200,
        )

    def test_register_response_matches_contract(self, client, db_session):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "contract_user",
                "email": "contract_user@example.com",
                "password": "StrongPass123!",
            },
        )
        assert response.status_code == 201
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/register",
            method="post",
            status_code=201,
        )

    def test_login_response_matches_contract(self, client, db_session, user_factory):
        user_factory(
            username="contract_login",
            email="contract_login@example.com",
            password="StrongPass123!",
        )
        response = client.post(
            "/api/auth/login",
            json={"username": "contract_login", "password": "StrongPass123!"},
        )
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/login",
            method="post",
            status_code=200,
        )

    def test_verify_error_response_matches_contract(self, client, db_session):
        response = client.get("/api/auth/verify")
        assert response.status_code == 401
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/auth/verify",
            method="get",
            status_code=401,
        )

