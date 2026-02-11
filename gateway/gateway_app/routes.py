"""Gateway proxy routes."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from flask import Blueprint, Response, current_app, jsonify, request

logger = logging.getLogger(__name__)

gateway_bp = Blueprint("gateway", __name__)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filtered_request_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS or lower == "host" or lower == "content-length":
            continue
        headers[name] = value
    return headers


def _rewrite_location(location: str) -> str:
    parsed = urlparse(location)
    if not parsed.scheme or not parsed.netloc:
        return location

    new_parsed = ParseResult(
        scheme=request.scheme,
        netloc=request.host,
        path=parsed.path,
        params=parsed.params,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return new_parsed.geturl()


def _set_response_headers(response: Response, downstream_response: Any) -> None:
    for name, value in downstream_response.headers.items():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS:
            continue
        if lower in {"content-length", "set-cookie", "location"}:
            continue
        response.headers[name] = value

    location = downstream_response.headers.get("Location")
    if location:
        response.headers["Location"] = _rewrite_location(location)

    set_cookie_values: list[str] = []
    raw = getattr(downstream_response, "raw", None)
    raw_headers = getattr(raw, "headers", None)
    if raw_headers is not None and hasattr(raw_headers, "getlist"):
        set_cookie_values = list(raw_headers.getlist("Set-Cookie"))
    elif "Set-Cookie" in downstream_response.headers:
        set_cookie_values = [downstream_response.headers["Set-Cookie"]]

    for cookie_header in set_cookie_values:
        response.headers.add("Set-Cookie", cookie_header)


def proxy_request(target_base_url: str, downstream_path: str) -> tuple[Response, int]:
    target_url = urljoin(
        target_base_url.rstrip("/") + "/",
        downstream_path.lstrip("/"),
    )
    logger.info("Proxying %s %s -> %s", request.method, request.path, target_url)

    try:
        downstream_response = requests.request(
            method=request.method,
            url=target_url,
            headers=_filtered_request_headers(),
            params=request.args,
            data=request.get_data(),
            allow_redirects=False,
            timeout=current_app.config["PROXY_TIMEOUT"],
        )
    except requests.Timeout:
        return jsonify({"error": "Downstream request timed out"}), 502
    except requests.RequestException:
        return jsonify({"error": "Downstream service unavailable"}), 502

    response = Response(
        downstream_response.content,
        status=downstream_response.status_code,
    )
    _set_response_headers(response, downstream_response)
    return response, downstream_response.status_code


@gateway_bp.route("/api/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    return jsonify({"status": "healthy", "service": "gateway"}), 200


@gateway_bp.route("/api/auth", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route(
    "/api/auth/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def proxy_auth(path: str) -> tuple[Response, int]:
    downstream_path = f"/api/auth/{path}" if path else "/api/auth"
    return proxy_request(current_app.config["AUTH_SERVICE_URL"], downstream_path)


@gateway_bp.route("/api/tasks", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route(
    "/api/tasks/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def proxy_tasks(path: str) -> tuple[Response, int]:
    downstream_path = f"/api/tasks/{path}" if path else "/api/tasks"
    return proxy_request(current_app.config["TASK_SERVICE_URL"], downstream_path)


@gateway_bp.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy_views(path: str) -> tuple[Response, int]:
    downstream_path = f"/{path}" if path else "/"
    return proxy_request(current_app.config["TASK_SERVICE_URL"], downstream_path)

