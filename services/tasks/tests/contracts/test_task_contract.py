"""Provider-side contract tests for task service."""

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
    return Path(__file__).resolve().parents[4] / "contracts" / "tasks_openapi.yaml"


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
    openapi_spec: dict[str, Any],
    path_template: str,
    method: str,
    status_code: int,
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
    def test_openapi_document_is_valid(self) -> None:
        openapi_spec_validator.validate(_load_openapi_spec())


class TestTaskProviderResponsesMatchContract:
    def test_health_response_matches_contract(self, client, db_session):
        response = client.get("/api/health")
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
        response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )
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
        create_response = client.post(
            "/api/tasks",
            data=json.dumps(valid_task_data),
            headers=api_headers,
        )
        assert create_response.status_code == 201

        response = client.get("/api/tasks", headers=api_headers)
        assert response.status_code == 200
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/tasks",
            method="get",
            status_code=200,
        )

    def test_unauthorized_error_response_matches_contract(self, client, db_session):
        response = client.get("/api/tasks")
        assert response.status_code == 401
        _assert_payload_matches_response_schema(
            payload=response.get_json(),
            path_template="/api/tasks",
            method="get",
            status_code=401,
        )

