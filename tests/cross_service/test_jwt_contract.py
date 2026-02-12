"""
Cross-Service JWT Contract Tests.

These tests verify that the auth service and task service agree on the
JWT "contract" -- the algorithm, required claims, expiration rules, and
clock-skew tolerance.  A contract test catches integration bugs early:
if the auth service starts issuing tokens with a new claim layout, the
task service's verifier will reject them, and these tests will fail
before anything reaches production.

Key SDET Concepts Demonstrated:
- Contract testing between independently deployed microservices
- Positive path: auth-issued tokens accepted by the task verifier
- Negative path: missing claims, wrong algorithms, expired tokens
- Loading a shared contract spec (YAML) as the single source of truth
- Algorithm confusion attacks (none / RS256 injection)
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import yaml

from services.auth.auth_app.jwt import create_token
from services.tasks.task_app.auth import verify_token

pytestmark = pytest.mark.cross_service


def _load_jwt_contract() -> dict:
    """Load the shared JWT contract YAML that both services must honour."""
    contract_path = Path(__file__).resolve().parents[2] / "contracts" / "jwt_contract.yaml"
    with contract_path.open("r", encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)["jwt_contract"]


def _to_base64_url(data: dict) -> str:
    """Encode a dict as a base64url JSON segment (no padding)."""
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _make_rs256_header_token(payload: dict) -> str:
    """Build a forged token with an RS256 header to test algorithm confusion."""
    # Signature bytes are irrelevant here; task/auth should reject by algorithm allowlist.
    header = {"alg": "RS256", "typ": "JWT"}
    return f"{_to_base64_url(header)}.{_to_base64_url(payload)}.invalidsig"


def test_auth_issued_token_matches_required_claim_types(jwt_secret):
    """Test that auth-issued tokens contain all contract-required claim types."""
    # Arrange
    contract = _load_jwt_contract()
    token = create_token(1, "contract_user", jwt_secret, 1)

    # Act
    payload = jwt.decode(token, jwt_secret, algorithms=[contract["algorithm"]])

    # Assert
    assert isinstance(payload["user_id"], int)
    assert payload["user_id"] > 0
    assert isinstance(payload["username"], str)
    assert payload["username"]
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)


def test_auth_issued_token_is_accepted_by_task_verifier(task_service_app, jwt_secret):
    """Test that a token minted by auth is accepted by the task verifier."""
    # Arrange
    token = create_token(42, "alice", jwt_secret, 1)

    # Act
    with task_service_app.app_context():
        payload = verify_token(token, jwt_secret, algorithms=["HS256"])

    # Assert
    assert payload is not None
    assert payload["user_id"] == 42
    assert payload["username"] == "alice"


def test_token_with_unknown_claims_is_accepted(task_service_app, jwt_secret):
    """Test that extra claims do not break verification (forward-compatible)."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 7,
        "username": "future_safe",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "tenant": "demo",
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    # Act
    with task_service_app.app_context():
        decoded = verify_token(token, jwt_secret, algorithms=["HS256"])

    # Assert
    assert decoded is not None
    assert decoded["tenant"] == "demo"


def test_missing_user_id_claim_is_rejected(task_service_app, jwt_secret):
    """Test that a token without the required user_id claim is rejected."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "username": "missing_user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    # Act
    with task_service_app.app_context():
        decoded = verify_token(token, jwt_secret, algorithms=["HS256"])

    # Assert
    assert decoded is None


def test_missing_exp_claim_is_rejected(task_service_app, jwt_secret):
    """Test that a token without an exp claim is rejected as non-expiring."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 1,
        "username": "missing_exp",
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    # Act
    with task_service_app.app_context():
        decoded = verify_token(token, jwt_secret, algorithms=["HS256"])

    # Assert
    assert decoded is None


def test_wrong_algorithms_none_and_rs256_are_rejected_by_both_services(
    auth_client,
    task_service_app,
    jwt_secret,
):
    """Test that 'none' and RS256 algorithm tokens are rejected by both services."""
    # Arrange
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": 5,
        "username": "alg_test",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    none_token = jwt.encode(payload, "", algorithm="none")
    rs256_header_token = _make_rs256_header_token(payload)

    # Act & Assert -- task service rejects both algorithm-confused tokens
    with task_service_app.app_context():
        assert verify_token(none_token, jwt_secret, algorithms=["HS256"]) is None
        assert verify_token(rs256_header_token, jwt_secret, algorithms=["HS256"]) is None

    # Act & Assert -- auth service also rejects both via its verify endpoint
    for token in [none_token, rs256_header_token]:
        response = auth_client.get(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid or expired token"}


def test_clock_skew_tolerance_is_respected(task_service_app, jwt_secret):
    """Test that tokens within clock-skew leeway pass but beyond it fail."""
    # Arrange
    now = datetime.now(timezone.utc)
    leeway_seconds = _load_jwt_contract()["clock_skew_tolerance_seconds"]

    within_skew_payload = {
        "user_id": 1,
        "username": "within",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=leeway_seconds - 5)).timestamp()),
    }
    beyond_skew_payload = {
        "user_id": 1,
        "username": "beyond",
        "iat": int((now - timedelta(minutes=2)).timestamp()),
        "exp": int((now - timedelta(seconds=leeway_seconds + 5)).timestamp()),
    }

    within_token = jwt.encode(within_skew_payload, jwt_secret, algorithm="HS256")
    beyond_token = jwt.encode(beyond_skew_payload, jwt_secret, algorithm="HS256")

    # Act & Assert
    with task_service_app.app_context():
        assert verify_token(within_token, jwt_secret, algorithms=["HS256"]) is not None
        assert verify_token(beyond_token, jwt_secret, algorithms=["HS256"]) is None


def test_malformed_token_is_rejected(task_service_app, jwt_secret):
    """Test that a structurally invalid token string is safely rejected."""
    # Arrange
    bad_token = "malformed.token"

    # Act
    with task_service_app.app_context():
        decoded = verify_token(bad_token, jwt_secret, algorithms=["HS256"])

    # Assert
    assert decoded is None
