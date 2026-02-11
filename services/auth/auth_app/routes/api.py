"""Auth service API endpoints."""

from __future__ import annotations

import os
from typing import Any

import jwt as pyjwt
from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select

from auth_app import db
from auth_app.jwt import create_token
from auth_app.models import User

api_bp = Blueprint("auth_api", __name__)

REQUIRED_TOKEN_CLAIMS = ["user_id", "username", "iat", "exp"]


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status_code


def _validate_required_fields(
    data: dict[str, Any], required_fields: list[str]
) -> str | None:
    for field in required_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"'{field}' is required"
    return None


def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def _decode_token(token: str) -> dict[str, Any]:
    payload = pyjwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
        options={"require": REQUIRED_TOKEN_CLAIMS},
        leeway=current_app.config.get("JWT_CLOCK_SKEW_SECONDS", 30),
    )
    if not isinstance(payload.get("user_id"), int) or payload["user_id"] <= 0:
        raise pyjwt.InvalidTokenError("Invalid user_id claim")
    if not isinstance(payload.get("username"), str) or not payload["username"].strip():
        raise pyjwt.InvalidTokenError("Invalid username claim")
    return payload


@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    return jsonify(
        {
            "status": "healthy",
            "service": "auth",
            "environment": os.getenv("ENVIRONMENT", "unknown"),
        }
    ), 200


@api_bp.route("/register", methods=["POST"])
def register() -> tuple[Response, int]:
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
        secret=current_app.config["JWT_SECRET_KEY"],
        expiry_hours=current_app.config["JWT_EXPIRY_HOURS"],
    )
    return jsonify({"token": token, "user": user.to_dict()}), 200


@api_bp.route("/verify", methods=["GET"])
def verify() -> tuple[Response, int]:
    token = _extract_bearer_token()
    if token is None:
        return _json_error("Missing or invalid Authorization header", 401)

    try:
        payload = _decode_token(token)
    except pyjwt.InvalidTokenError:
        return _json_error("Invalid or expired token", 401)

    return jsonify({"user_id": payload["user_id"], "username": payload["username"]}), 200

