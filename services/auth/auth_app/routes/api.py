"""
Auth service API endpoints.

Implements the RESTful HTTP interface for the authentication micro-service.
All routes are mounted on the ``auth_api`` blueprint and are typically
served under the ``/api/auth`` URL prefix by the application factory.

Endpoints:
    GET  /health    -- Liveness / readiness probe for orchestration tools.
    POST /register  -- Create a new user account.
    POST /login     -- Authenticate and receive a JWT.
    GET  /verify    -- Validate a Bearer token and return its identity claims.

Key Concepts Demonstrated:
- Blueprint-based route organisation
- JWT verification with claim validation
- Input validation before database access
- Consistent JSON error responses
- Bearer token extraction from the Authorization header
"""

from __future__ import annotations

import os
from typing import Any

import jwt as pyjwt
from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select

from .. import db
from ..jwt import create_token
from ..models import User

api_bp = Blueprint("auth_api", __name__)

# Every JWT produced by this service MUST contain these four claims.
# The ``require`` option passed to ``pyjwt.decode`` will reject tokens
# that are missing any of them before signature verification completes.
REQUIRED_TOKEN_CLAIMS = ["user_id", "username", "iat", "exp"]


# =====================================================================
# Helper Functions
# =====================================================================


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    """
    Build a standardised JSON error response.

    Wrapping error responses in a single helper ensures a consistent
    ``{"error": "..."}`` envelope across every endpoint.

    Args:
        message: Human-readable description of the error.
        status_code: HTTP status code to return.

    Returns:
        A ``(Response, int)`` tuple suitable for returning directly
        from a Flask view function.
    """
    return jsonify({"error": message}), status_code


def _validate_required_fields(
    data: dict[str, Any], required_fields: list[str]
) -> str | None:
    """
    Check that all *required_fields* are present and non-blank in *data*.

    Validates that each field exists, is a string, and contains at least
    one non-whitespace character.

    Args:
        data: The parsed JSON request body.
        required_fields: List of field names that must be present.

    Returns:
        An error message string describing the first missing or blank
        field, or ``None`` if all required fields are valid.
    """
    for field in required_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"'{field}' is required"
    return None


def _extract_bearer_token() -> str | None:
    """
    Extract the Bearer token from the current request's Authorization header.

    Looks for a header of the form ``Authorization: Bearer <token>`` and
    returns the token portion.  Returns ``None`` if the header is absent,
    malformed, or empty after stripping whitespace.

    Returns:
        The raw JWT string, or ``None`` if no valid Bearer token is present.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def _decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an RS256 JWT issued by this service.

    Verifies the signature, checks expiration, ensures all required claims
    are present, and performs semantic validation on the identity claims
    (``user_id`` must be a positive int, ``username`` must be non-blank).

    Args:
        token: The raw compact-JWS token string.

    Returns:
        The decoded payload dictionary with validated claims.

    Raises:
        pyjwt.InvalidTokenError: If the token is expired, malformed, has
            an invalid signature, or fails claim validation.
    """
    payload = pyjwt.decode(
        token,
        current_app.config["JWT_PUBLIC_KEY"],
        algorithms=["RS256"],
        options={"require": REQUIRED_TOKEN_CLAIMS},
        # leeway accounts for small clock differences between the machine
        # that issued the token and the machine verifying it.  Without
        # leeway, a token created on a server whose clock is a few seconds
        # ahead could be rejected as "not yet valid" by a verifier.
        leeway=current_app.config.get("JWT_CLOCK_SKEW_SECONDS", 30),
    )
    if not isinstance(payload.get("user_id"), int) or payload["user_id"] <= 0:
        raise pyjwt.InvalidTokenError("Invalid user_id claim")
    if not isinstance(payload.get("username"), str) or not payload["username"].strip():
        raise pyjwt.InvalidTokenError("Invalid username claim")
    return payload


# =====================================================================
# API Endpoints
# =====================================================================


@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """
    Liveness / readiness health-check endpoint.

    Returns a simple JSON object indicating the service is running.
    Orchestration tools (Docker health-checks, Kubernetes probes, load
    balancers) poll this endpoint to decide whether to route traffic to
    the instance.

    Returns:
        A 200 JSON response with ``status``, ``service``, and
        ``environment`` fields.
    """
    return jsonify(
        {
            "status": "healthy",
            "service": "auth",
            "environment": os.getenv("ENVIRONMENT", "unknown"),
        }
    ), 200


@api_bp.route("/register", methods=["POST"])
def register() -> tuple[Response, int]:
    """
    Register a new user account.

    Expects a JSON body with ``username``, ``email``, and ``password``.
    Validates input, checks for duplicate username or email, hashes the
    password, and persists the new user.

    Returns:
        201 with the created user dict on success.
        400 if required fields are missing or exceed length limits.
        409 if the username or email is already taken.
    """
    data = request.get_json(silent=True) or {}
    missing = _validate_required_fields(data, ["username", "email", "password"])
    if missing:
        return _json_error(missing, 400)

    username = data["username"].strip()
    email = data["email"].strip()
    password = data["password"]

    if len(username) > 80:
        return _json_error("username must be 80 characters or less", 400)
    if len(email) > 120:
        return _json_error("email must be 120 characters or less", 400)

    existing_user = db.session.scalar(select(User).where(User.username == username))
    if existing_user:
        return _json_error("Username already exists", 409)

    existing_email = db.session.scalar(select(User).where(User.email == email))
    if existing_email:
        return _json_error("Email already exists", 409)

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"user": user.to_dict()}), 201


@api_bp.route("/login", methods=["POST"])
def login() -> tuple[Response, int]:
    """
    Authenticate a user and issue a JWT.

    Expects a JSON body with ``username`` and ``password``.  On success
    a signed JWT and the user's public profile are returned.  The
    deliberately vague ``"Invalid username or password"`` message avoids
    revealing whether the username exists.

    Returns:
        200 with ``token`` and ``user`` on success.
        400 if required fields are missing.
        401 if credentials are incorrect.
    """
    data = request.get_json(silent=True) or {}
    missing = _validate_required_fields(data, ["username", "password"])
    if missing:
        return _json_error(missing, 400)

    username = data["username"].strip()
    password = data["password"]
    user = db.session.scalar(select(User).where(User.username == username))

    if not user or not user.check_password(password):
        return _json_error("Invalid username or password", 401)

    token = create_token(
        user_id=user.id,
        username=user.username,
        private_key=current_app.config["JWT_PRIVATE_KEY"],
        expiry_hours=current_app.config["JWT_EXPIRY_HOURS"],
    )
    return jsonify({"token": token, "user": user.to_dict()}), 200


@api_bp.route("/verify", methods=["GET"])
def verify() -> tuple[Response, int]:
    """
    Verify a Bearer JWT and return the embedded identity claims.

    Other micro-services call this endpoint to confirm that a token is
    valid and to retrieve the ``user_id`` and ``username`` without
    needing direct access to the JWT private key.

    Returns:
        200 with ``user_id`` and ``username`` if the token is valid.
        401 if the Authorization header is missing or the token is
        invalid / expired.
    """
    token = _extract_bearer_token()
    if token is None:
        return _json_error("Missing or invalid Authorization header", 401)

    try:
        payload = _decode_token(token)
    except pyjwt.InvalidTokenError:
        return _json_error("Invalid or expired token", 401)

    return jsonify({"user_id": payload["user_id"], "username": payload["username"]}), 200
