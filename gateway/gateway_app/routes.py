"""
Gateway Reverse-Proxy Routes.

This module implements the core reverse-proxy logic of the API gateway.
Every inbound HTTP request is matched by a Flask route, forwarded to the
appropriate downstream microservice (auth-service, task-service API, or
frontend-service), and
the downstream response is relayed back to the caller — transparently.

Because the gateway sits between the client and the real services it must
handle several HTTP concerns that a normal web application never sees:

  * **Hop-by-hop headers** — certain HTTP/1.1 headers are meaningful only
    for a single transport-level connection and must never be forwarded to
    the next hop (RFC 2616 §13.5.1, RFC 7230 §6.1).
  * **Header rewriting** — the ``Host`` and ``Content-Length`` headers
    sent by the client describe *this* gateway; forwarding them verbatim
    would confuse the downstream service.
  * **Location rewriting** — when a downstream service issues a redirect,
    the ``Location`` URL points at the *internal* service address.  The
    gateway rewrites it so the client is redirected through the gateway.
  * **Timeout / error protection** — if a downstream service is slow or
    unreachable the gateway returns a 502 Bad Gateway rather than hanging.

Key Concepts Demonstrated:
- Reverse-proxy pattern: transparent request/response forwarding
- Hop-by-hop header filtering per the HTTP/1.1 specification
- Location-header rewriting for redirect transparency
- Defensive timeout handling to avoid cascading failures
- Blueprint-based catch-all routing for web UI passthrough
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from flask import Blueprint, Response, current_app, jsonify, request

logger = logging.getLogger(__name__)

gateway_bp = Blueprint("gateway", __name__)

# =====================================================================
# Constants
# =====================================================================

# Hop-by-hop headers are defined by the HTTP/1.1 specification (RFC 2616
# §13.5.1, updated by RFC 7230 §6.1).  They describe properties of a
# *single* transport connection — e.g. whether to keep the TCP socket
# open ("keep-alive"), how the body is chunked ("transfer-encoding"), or
# authentication for the proxy itself ("proxy-authenticate").  A proxy
# MUST NOT forward these to the next hop because they would be
# misinterpreted by the downstream server or the client.
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

# =====================================================================
# Header Helpers
# =====================================================================


def _filtered_request_headers() -> dict[str, str]:
    """
    Build a clean header dict to send to the downstream service.

    Three categories of headers are intentionally dropped:

    1. **Hop-by-hop headers** — connection-specific; see ``HOP_BY_HOP_HEADERS``.
    2. **Host** — the client's ``Host`` value refers to the *gateway*
       address.  Forwarding it would cause virtual-host routing issues on
       the downstream service; ``requests`` will set the correct Host
       automatically from the target URL.
    3. **Content-Length** — the ``requests`` library recalculates this
       from the actual body we pass.  Forwarding the original could cause
       a length mismatch if the body was re-encoded in transit.

    Returns:
        A dictionary of headers safe to forward to the downstream service.
    """
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS or lower == "host" or lower == "content-length":
            continue
        headers[name] = value
    return headers


def _rewrite_location(location: str) -> str:
    """
    Rewrite a downstream ``Location`` header so it routes through the gateway.

    When a downstream service returns a redirect (3xx), the ``Location``
    URL contains the *internal* service address (e.g.
    ``http://auth-service:5000/login``).  If forwarded as-is, the
    client would try to reach that internal address — which is
    unreachable from outside the cluster.  This helper replaces the
    scheme and host with the gateway's own externally-visible origin so
    the client seamlessly follows the redirect through the gateway.

    Relative or partial URLs (no scheme / no netloc) are returned
    unchanged because they will already resolve relative to the gateway.

    Args:
        location: The raw ``Location`` header value from the downstream
            response.

    Returns:
        The rewritten URL with the gateway's scheme and host, or the
        original value if no rewriting is needed.
    """
    parsed = urlparse(location)
    # Relative URLs already resolve against the gateway — nothing to do.
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
    """
    Copy downstream response headers onto the gateway ``Response``.

    Most headers are copied verbatim, with three exceptions:

    * **Hop-by-hop headers** — stripped for the same reason they are
      stripped on the request side (see ``HOP_BY_HOP_HEADERS``).
    * **Content-Length** — Flask will compute the correct value from the
      actual body we attached to the ``Response`` object.
    * **Location** — rewritten via ``_rewrite_location`` so redirects
      always point back through the gateway.
    * **Set-Cookie** — handled specially below because the high-level
      ``headers`` dict only returns the *last* ``Set-Cookie`` value; we
      need every individual cookie header.

    Args:
        response: The outgoing Flask ``Response`` to populate.
        downstream_response: The ``requests.Response`` from the
            downstream service.
    """
    for name, value in downstream_response.headers.items():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS:
            continue
        # These three headers receive special handling below — skip the
        # generic copy so we don't double-set or forward stale values.
        if lower in {"content-length", "set-cookie", "location"}:
            continue
        response.headers[name] = value

    # Rewrite Location so redirects route back through the gateway.
    location = downstream_response.headers.get("Location")
    if location:
        response.headers["Location"] = _rewrite_location(location)

    # Set-Cookie must be copied from the *raw* urllib3 response because
    # the high-level requests API merges duplicate headers and only
    # exposes the last one.  Using ``raw.headers.getlist`` preserves
    # every Set-Cookie header the downstream service sent.
    set_cookie_values: list[str] = []
    raw = getattr(downstream_response, "raw", None)
    raw_headers = getattr(raw, "headers", None)
    if raw_headers is not None and hasattr(raw_headers, "getlist"):
        set_cookie_values = list(raw_headers.getlist("Set-Cookie"))
    elif "Set-Cookie" in downstream_response.headers:
        set_cookie_values = [downstream_response.headers["Set-Cookie"]]

    # Explicitly add each cookie header to the Flask response so the
    # browser receives (and stores) every cookie the downstream service set.
    for cookie_header in set_cookie_values:
        response.headers.add("Set-Cookie", cookie_header)

# =====================================================================
# Proxy Logic
# =====================================================================


def proxy_request(target_base_url: str, downstream_path: str) -> tuple[Response, int]:
    """
    Forward the current Flask request to a downstream service and relay the response.

    This is the heart of the reverse-proxy: it rebuilds the outgoing
    request (method, headers, query-string, body), sends it to the
    downstream service, and wraps the result in a Flask ``Response``.

    ``allow_redirects=False`` is critical — the gateway must return
    redirects to the *client* (after rewriting ``Location``) rather than
    silently following them, which would hide the redirect from the
    caller and break browser navigation.

    Args:
        target_base_url: The root URL of the downstream service
            (e.g. ``"http://auth-service:5000"``).
        downstream_path: The path portion to append
            (e.g. ``"/api/auth/login"``).

    Returns:
        A ``(Response, status_code)`` tuple suitable for returning
        directly from a Flask view function.
    """
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
        # Return 502 Bad Gateway — the downstream service is reachable
        # but took too long.  A 504 would also be defensible, but 502
        # is conventional for simple reverse-proxy implementations.
        return jsonify({"error": "Downstream request timed out"}), 502
    except requests.RequestException:
        # Any other transport-level failure (DNS resolution, connection
        # refused, TLS error, etc.) also surfaces as 502 so the client
        # knows the problem is between the gateway and the backend, not
        # with their own request.
        return jsonify({"error": "Downstream service unavailable"}), 502

    response = Response(
        downstream_response.content,
        status=downstream_response.status_code,
    )
    _set_response_headers(response, downstream_response)
    return response, downstream_response.status_code

# =====================================================================
# Route Handlers
# =====================================================================


@gateway_bp.route("/api/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """
    Shallow health probe for the gateway itself.

    Returns a 200 with a simple JSON body so that load balancers and
    orchestration systems can verify the gateway process is alive.  This
    endpoint is *not* proxied — it answers from the gateway directly.

    Returns:
        A JSON ``{"status": "healthy", "service": "gateway"}`` response
        with HTTP 200.
    """
    return jsonify({"status": "healthy", "service": "gateway"}), 200


@gateway_bp.route("/api/auth", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route(
    "/api/auth/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def proxy_auth(path: str) -> tuple[Response, int]:
    """
    Forward all ``/api/auth/...`` requests to the auth-service.

    Args:
        path: The sub-path after ``/api/auth/`` (captured by Flask's
            ``<path:path>`` converter).  An empty string when the
            client hits ``/api/auth`` with no trailing path.

    Returns:
        The proxied response and status code from the auth-service.
    """
    downstream_path = f"/api/auth/{path}" if path else "/api/auth"
    return proxy_request(current_app.config["AUTH_SERVICE_URL"], downstream_path)


@gateway_bp.route("/api/tasks", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route(
    "/api/tasks/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def proxy_tasks(path: str) -> tuple[Response, int]:
    """
    Forward all ``/api/tasks/...`` requests to the task-service.

    Args:
        path: The sub-path after ``/api/tasks/`` (captured by Flask's
            ``<path:path>`` converter).  An empty string when the
            client hits ``/api/tasks`` with no trailing path.

    Returns:
        The proxied response and status code from the task-service.
    """
    downstream_path = f"/api/tasks/{path}" if path else "/api/tasks"
    return proxy_request(current_app.config["TASK_SERVICE_URL"], downstream_path)


# Catch-all: any request that does NOT match ``/api/auth`` or ``/api/tasks``
# is forwarded to the frontend-service. This allows the frontend BFF to serve
# web UI pages (HTML, static assets, form routes) through the gateway
# without requiring an explicit route for every possible frontend path.
@gateway_bp.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@gateway_bp.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy_views(path: str) -> tuple[Response, int]:
    """
    Catch-all route — forward unmatched paths to the frontend-service web UI.

    Flask evaluates routes in registration order, so the more-specific
    ``/api/auth`` and ``/api/tasks`` routes are matched first. Anything
    that falls through lands here and is proxied to the frontend-service,
    which serves browser-facing HTML pages and static assets.

    Args:
        path: The full request path (may be empty for ``/``).

    Returns:
        The proxied response and status code from the frontend-service.
    """
    downstream_path = f"/{path}" if path else "/"
    return proxy_request(current_app.config["FRONTEND_SERVICE_URL"], downstream_path)
