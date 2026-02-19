"""
HTML view routes for the frontend BFF service.

Implements all user-facing routes for the task management UI.  Each route
handler renders a Jinja template and, when necessary, proxies requests to
the auth or task micro-services over HTTP.  The module is organised into
three logical sections:

1. **Helper functions** -- URL builders, token verification, API call
   wrappers, and response parsers that keep the route handlers concise.
2. **Authentication routes** -- login, registration, and logout flows
   that coordinate with the auth service.
3. **Task CRUD routes** -- list, create, view, edit, update, delete, and
   quick-status-change operations that delegate to the task service.

Every task-mutating route is protected by the ``login_required`` decorator,
which verifies the JWT stored in the Flask session cookie before allowing
the request through.

Key Concepts Demonstrated:
- Backend-for-Frontend (BFF) request proxying
- Server-side session management with JWTs
- Decorator-based access control (``login_required``)
- Graceful error handling for downstream service failures
- Flash-message feedback for form submissions
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any

import requests
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..auth import verify_token
from ..models import TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


# =====================================================================
# Helper Functions
# =====================================================================


def _auth_service_url(path: str) -> str:
    """
    Build a full URL to an auth service endpoint.

    Joins the configured ``AUTH_SERVICE_URL`` base with the given *path*,
    stripping/adding slashes as needed to avoid double-slash issues.

    Args:
        path: Relative path to the auth endpoint (e.g. ``"/api/auth/login"``).

    Returns:
        Absolute URL string suitable for use with :mod:`requests`.
    """
    return f"{current_app.config['AUTH_SERVICE_URL'].rstrip('/')}/{path.lstrip('/')}"


def _task_service_url(path: str) -> str:
    """
    Build a full URL to a task service endpoint.

    Joins the configured ``TASK_SERVICE_URL`` base with the given *path*,
    stripping/adding slashes as needed to avoid double-slash issues.

    Args:
        path: Relative path to the task endpoint (e.g. ``"/api/tasks"``).

    Returns:
        Absolute URL string suitable for use with :mod:`requests`.
    """
    return f"{current_app.config['TASK_SERVICE_URL'].rstrip('/')}/{path.lstrip('/')}"


def _verify_session_token() -> dict[str, Any] | None:
    """
    Verify the JWT stored in the Flask session cookie.

    Retrieves the ``auth_token`` value from the server-side session and
    passes it through ``verify_token`` for cryptographic and semantic
    validation.

    Returns:
        The decoded JWT payload dictionary on success, or ``None`` if no
        token is stored or the token is invalid/expired.
    """
    token = session.get("auth_token")
    if not token:
        return None
    return verify_token(token, current_app.config["JWT_PUBLIC_KEY"], algorithms=["RS256"])


def _task_service_headers() -> dict[str, str]:
    """
    Build authorization headers for calls to the task service API.

    Extracts the JWT from the Flask session and wraps it in a
    ``Bearer`` Authorization header so the task service can verify the
    caller's identity.

    Returns:
        A dictionary with the ``Authorization`` header, or an empty
        dictionary if no session token is present.
    """
    token = session.get("auth_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _call_task_api(method: str, path: str, **kwargs) -> requests.Response:
    """
    Call the task service API with a per-service timeout and auth header.

    Centralises HTTP communication with the task micro-service so that
    every call automatically includes the JWT authorization header and
    respects the configured timeout.

    Args:
        method: HTTP method (``"GET"``, ``"POST"``, ``"PUT"``, etc.).
        path: Relative path to the task endpoint (e.g. ``"/api/tasks"``).
        **kwargs: Additional keyword arguments forwarded to
            :func:`requests.request` (e.g. ``json``, ``params``).

    Returns:
        The :class:`requests.Response` from the task service.

    Raises:
        requests.Timeout: If the task service does not respond within
            the configured ``TASK_SERVICE_TIMEOUT``.
        requests.RequestException: For network-level failures.
    """
    url = _task_service_url(path)
    extra_headers = kwargs.pop("headers", {})
    headers = {**extra_headers, **_task_service_headers()}
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        timeout=current_app.config["TASK_SERVICE_TIMEOUT"],
        **kwargs,
    )


def _parse_iso_datetime(iso_string: str | None) -> datetime | None:
    """
    Parse an ISO-8601 datetime string returned by the task API.

    Handles the ``Z`` suffix (common in JSON APIs) by replacing it with
    the equivalent ``+00:00`` offset that :meth:`datetime.fromisoformat`
    understands.

    Args:
        iso_string: An ISO-8601 formatted string, or ``None``.

    Returns:
        A :class:`datetime` object, or ``None`` if the input was
        ``None``, empty, or could not be parsed.
    """
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return None


def _deserialize_task(data: dict[str, Any]) -> dict[str, Any]:
    """
    Convert an API task payload into a template-friendly dictionary.

    Parses ISO-8601 date strings (``due_date``, ``created_at``,
    ``updated_at``) into native :class:`datetime` objects so that Jinja
    filters like ``|datetimeformat`` can be used in templates.

    Args:
        data: Raw task dictionary returned by the task service JSON API.

    Returns:
        A shallow copy of *data* with date fields replaced by
        :class:`datetime` instances (or ``None`` if absent/unparseable).
    """
    task = dict(data)
    task["due_date"] = _parse_iso_datetime(task.get("due_date"))
    task["created_at"] = _parse_iso_datetime(task.get("created_at"))
    task["updated_at"] = _parse_iso_datetime(task.get("updated_at"))
    return task


def _response_error_message(response: requests.Response, default: str) -> str:
    """
    Extract an error message from a JSON API response if possible.

    Attempts to parse the response body as JSON and read its ``error``
    field.  Falls back to *default* when the body is not JSON or the
    field is missing/blank -- ensuring the caller always has a
    human-readable message for flash feedback.

    Args:
        response: The :class:`requests.Response` from a downstream
            service call.
        default: Fallback message returned when extraction fails.

    Returns:
        The extracted error string, or *default*.
    """
    try:
        payload = response.json()
    except ValueError:
        return default
    message = payload.get("error")
    if isinstance(message, str) and message.strip():
        return message
    return default


def _render_index(
    tasks: list[dict[str, Any]],
    *,
    status_filter: str,
    priority_filter: str,
    status_code: int = 200,
):
    """
    Render the task list index page with standard template context.

    Centralises the ``render_template`` call for the index page so that
    every code path (success, empty-list fallback, error recovery)
    provides the same set of template variables.

    Args:
        tasks: List of deserialised task dictionaries to display.
        status_filter: Currently active status filter value (or ``""``
            for no filter).
        priority_filter: Currently active priority filter value (or
            ``""`` for no filter).
        status_code: HTTP status code for the response (defaults to 200).

    Returns:
        A ``(body, status_code)`` tuple suitable for returning from a
        Flask view function.
    """
    return (
        render_template(
            "index.html",
            tasks=tasks,
            statuses=TaskStatus,
            priorities=TaskPriority,
            current_status=status_filter,
            current_priority=priority_filter,
            current_username=g.username,
        ),
        status_code,
    )


def ensure_utc(value: datetime) -> datetime:
    """
    Normalise a datetime to UTC.

    Naive datetimes (no ``tzinfo``) are assumed to already represent UTC
    and have the timezone attached.  Aware datetimes are converted.

    Args:
        value: The datetime to normalise.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def login_required(view_func):
    """
    Decorator that requires a valid JWT in session for view routes.

    Verifies the session token before calling the wrapped view.  On
    success the decoded ``user_id`` and ``username`` are stashed on
    Flask's ``g`` object so that downstream code can access them without
    re-verifying.  On failure the session is cleared and the user is
    redirected to the login page.

    Args:
        view_func: The Flask view function to protect.

    Returns:
        The decorated view function.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        payload = _verify_session_token()
        if payload is None:
            # Token missing or invalid -- clear stale session state and
            # bounce the user to the login form.
            session.pop("auth_token", None)
            return redirect(url_for("views.login"))

        g.user_id = payload["user_id"]
        g.username = payload["username"]
        return view_func(*args, **kwargs)

    return wrapper


# =====================================================================
# Authentication Routes
# =====================================================================


@views_bp.route("/health", methods=["GET"])
def health_check():
    """
    Return service health status.

    This endpoint is public (no authentication required) and is intended
    for load-balancer and orchestrator liveness probes.

    Returns:
        A 200 JSON response with ``status`` and ``service`` fields.
    """
    return {"status": "healthy", "service": "frontend"}, 200


@views_bp.route("/login", methods=["GET"])
def login():
    """
    Render the login page.

    If the user already has a valid session token, they are redirected
    straight to the task list instead of showing the login form.

    Returns:
        The rendered ``login.html`` template, or a redirect to the
        index page.
    """
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("login.html")


@views_bp.route("/login", methods=["POST"])
def login_submit():
    """
    Handle login form submission.

    Validates form fields, forwards credentials to the auth service's
    ``/api/auth/login`` endpoint, and on success stores the returned JWT
    in the Flask session cookie before redirecting to the task list.

    Returns:
        A redirect to the index page on success, or the re-rendered
        ``login.html`` template with a flash message on failure.
    """
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("login.html"), 400

    try:
        response = requests.post(
            _auth_service_url("/api/auth/login"),
            json={"username": username, "password": password},
            timeout=current_app.config["AUTH_SERVICE_TIMEOUT"],
        )
    except requests.Timeout:
        flash("Login service timed out. Please try again.", "error")
        return render_template("login.html"), 503
    except requests.RequestException:
        flash("Login service unavailable. Please try again later.", "error")
        return render_template("login.html"), 503

    if response.status_code == 200:
        token = response.json().get("token")
        if not token:
            flash("Invalid login response received.", "error")
            return render_template("login.html"), 502
        session["auth_token"] = token
        flash("Logged in successfully.", "success")
        return redirect(url_for("views.index"))

    if response.status_code == 401:
        flash("Invalid username or password.", "error")
        return render_template("login.html"), 401

    flash("Unexpected login error. Please try again.", "error")
    return render_template("login.html"), 502


@views_bp.route("/register", methods=["GET"])
def register():
    """
    Render the registration page.

    Already-authenticated users are redirected to the task list.

    Returns:
        The rendered ``register.html`` template, or a redirect to the
        index page.
    """
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("register.html")


@views_bp.route("/register", methods=["POST"])
def register_submit():
    """
    Handle registration form submission.

    Validates form fields and forwards the new account details to the
    auth service's ``/api/auth/register`` endpoint.  On success the user
    is redirected to the login page with a success flash message.

    Returns:
        A redirect to the login page on success, or the re-rendered
        ``register.html`` template with a flash message on failure.
    """
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("Username, email, and password are required.", "error")
        return render_template("register.html"), 400

    try:
        response = requests.post(
            _auth_service_url("/api/auth/register"),
            json={"username": username, "email": email, "password": password},
            timeout=current_app.config["AUTH_SERVICE_TIMEOUT"],
        )
    except requests.Timeout:
        flash("Registration service timed out. Please try again.", "error")
        return render_template("register.html"), 503
    except requests.RequestException:
        flash("Registration service unavailable. Please try again later.", "error")
        return render_template("register.html"), 503

    if response.status_code == 201:
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("views.login"))

    if response.status_code in {400, 409}:
        flash(_response_error_message(response, "Registration failed."), "error")
        return render_template("register.html"), response.status_code

    flash("Unexpected registration error. Please try again.", "error")
    return render_template("register.html"), 502


@views_bp.route("/logout", methods=["POST"])
def logout():
    """
    Clear the session token and redirect to the login page.

    Removes the ``auth_token`` from the Flask session cookie so that
    subsequent requests are treated as unauthenticated.

    Returns:
        A redirect to the login page with a confirmation flash message.
    """
    session.pop("auth_token", None)
    flash("Logged out. Session cleared.", "success")
    return redirect(url_for("views.login"))


# =====================================================================
# Task CRUD Routes
# =====================================================================


@views_bp.route("/")
@login_required
def index():
    """
    Render the task list page with optional status and priority filters.

    Reads ``status`` and ``priority`` query-string parameters and
    forwards them to the task service's ``GET /api/tasks`` endpoint.
    The response is deserialised into template-friendly dictionaries
    and rendered via ``index.html``.

    Returns:
        The rendered task list page, or an error-state page when the
        task service is unreachable.
    """
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    params: dict[str, str] = {}
    if status_filter:
        params["status"] = status_filter
    if priority_filter:
        params["priority"] = priority_filter

    try:
        response = _call_task_api("GET", "/api/tasks", params=params)
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return _render_index([], status_filter=status_filter, priority_filter=priority_filter, status_code=503)
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return _render_index([], status_filter=status_filter, priority_filter=priority_filter, status_code=503)

    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("views.login"))

    if response.status_code != 200:
        flash(_response_error_message(response, "Error loading tasks."), "error")
        return _render_index([], status_filter=status_filter, priority_filter=priority_filter, status_code=502)

    payload = response.json()
    tasks_data = payload.get("tasks", [])
    tasks = [_deserialize_task(task) for task in tasks_data]

    return _render_index(tasks, status_filter=status_filter, priority_filter=priority_filter)


@views_bp.route("/tasks/new")
@login_required
def new_task():
    """
    Render the empty task creation form.

    Passes ``task=None`` to the shared ``task_form.html`` template so
    that all form fields start blank and the submit action points to
    :func:`create_task`.

    Returns:
        The rendered ``task_form.html`` template.
    """
    return render_template(
        "task_form.html",
        task=None,
        statuses=TaskStatus,
        priorities=TaskPriority,
        form_action=url_for("views.create_task"),
        form_title="Create New Task",
    )


@views_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    """
    Handle task creation form submission.

    Validates form fields (title required, length limit, date format,
    positive estimated minutes), builds a JSON payload, and POSTs it to
    the task service's ``/api/tasks`` endpoint.

    Returns:
        A redirect to the index page on success, or back to the
        creation form with a flash message on validation/service error.
    """
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.new_task"))
    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.new_task"))

    description = request.form.get("description", "").strip()
    status = request.form.get("status", TaskStatus.PENDING.value)
    priority = request.form.get("priority", TaskPriority.MEDIUM.value)

    due_date = None
    due_date_str = request.form.get("due_date")
    if due_date_str:
        try:
            due_date = ensure_utc(datetime.fromisoformat(due_date_str))
        except ValueError:
            flash("Invalid date format", "error")
            return redirect(url_for("views.new_task"))

    estimated_minutes = None
    estimated_minutes_str = request.form.get("estimated_minutes")
    if estimated_minutes_str:
        try:
            estimated_minutes = int(estimated_minutes_str)
            if estimated_minutes < 1:
                flash("Estimated minutes must be a positive number", "error")
                return redirect(url_for("views.new_task"))
        except ValueError:
            flash("Invalid estimated minutes", "error")
            return redirect(url_for("views.new_task"))

    try:
        response = _call_task_api(
            "POST",
            "/api/tasks",
            json={
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "due_date": due_date.isoformat() if due_date else None,
                "estimated_minutes": estimated_minutes,
            },
        )
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.new_task"))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.new_task"))

    if response.status_code == 201:
        flash("Task created successfully", "success")
        return redirect(url_for("views.index"))
    if response.status_code == 400:
        flash(_response_error_message(response, "Invalid task data"), "error")
        return redirect(url_for("views.new_task"))
    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("views.login"))

    flash("Error creating task. Please try again.", "error")
    return redirect(url_for("views.new_task"))


def _get_task(task_id: int) -> dict[str, Any] | None:
    """
    Fetch a single task from the task API for the current user.

    Used by the view, edit, and update routes to load a task before
    rendering or modifying it.  Handles 401 responses by clearing the
    session and flashing an expiry message so that the caller can
    redirect appropriately.

    Args:
        task_id: The primary-key ID of the task to retrieve.

    Returns:
        A deserialised task dictionary on success, or ``None`` when the
        task is not found or the session has expired.

    Raises:
        RuntimeError: If the task service returns an unexpected status
            code (neither 200, 404, nor 401).
    """
    response = _call_task_api("GET", f"/api/tasks/{task_id}")
    if response.status_code == 200:
        return _deserialize_task(response.json())
    if response.status_code == 404:
        return None
    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return None
    raise RuntimeError(_response_error_message(response, "Failed to fetch task"))


@views_bp.route("/tasks/<int:task_id>")
@login_required
def view_task(task_id: int):
    """
    Render the task detail page.

    Fetches the task from the task service and displays it in the
    read-only ``task_detail.html`` template.  Aborts with 404 if the
    task does not exist or does not belong to the current user.

    Args:
        task_id: The primary-key ID of the task to display.

    Returns:
        The rendered ``task_detail.html`` template, a redirect on
        service error, or a 404 abort.
    """
    try:
        task = _get_task(task_id)
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.index"))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.index"))
    except RuntimeError as error:
        flash(str(error), "error")
        return redirect(url_for("views.index"))

    if task is None:
        # _get_task returns None for both 404 and expired-session cases.
        # When the session was cleared, redirect to login; otherwise 404.
        if session.get("auth_token") is None:
            return redirect(url_for("views.login"))
        abort(404)

    return render_template("task_detail.html", task=task, statuses=TaskStatus)


@views_bp.route("/tasks/<int:task_id>/edit")
@login_required
def edit_task(task_id: int):
    """
    Render the task edit form pre-populated with existing data.

    Fetches the task from the task service and passes it to the shared
    ``task_form.html`` template with the submit action pointing to
    :func:`update_task`.

    Args:
        task_id: The primary-key ID of the task to edit.

    Returns:
        The rendered ``task_form.html`` template, a redirect on service
        error, or a 404 abort.
    """
    try:
        task = _get_task(task_id)
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.index"))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.index"))
    except RuntimeError as error:
        flash(str(error), "error")
        return redirect(url_for("views.index"))

    if task is None:
        if session.get("auth_token") is None:
            return redirect(url_for("views.login"))
        abort(404)

    return render_template(
        "task_form.html",
        task=task,
        statuses=TaskStatus,
        priorities=TaskPriority,
        form_action=url_for("views.update_task", task_id=task_id),
        form_title="Edit Task",
    )


@views_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def update_task(task_id: int):
    """
    Handle the task edit form submission.

    Validates form fields, builds a JSON payload, and PUTs it to the
    task service's ``/api/tasks/<id>`` endpoint.  On success the user is
    redirected to the task detail page.

    Args:
        task_id: The primary-key ID of the task to update.

    Returns:
        A redirect to the task detail page on success, or back to the
        edit form with a flash message on validation/service error.
    """
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))
    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))

    description = request.form.get("description", "").strip()
    status = request.form.get("status", TaskStatus.PENDING.value)
    priority = request.form.get("priority", TaskPriority.MEDIUM.value)

    due_date = None
    due_date_str = request.form.get("due_date")
    if due_date_str:
        try:
            due_date = ensure_utc(datetime.fromisoformat(due_date_str))
        except ValueError:
            flash("Invalid date format", "error")
            return redirect(url_for("views.edit_task", task_id=task_id))

    estimated_minutes = None
    estimated_minutes_str = request.form.get("estimated_minutes")
    if estimated_minutes_str:
        try:
            estimated_minutes = int(estimated_minutes_str)
            if estimated_minutes < 1:
                flash("Estimated minutes must be a positive number", "error")
                return redirect(url_for("views.edit_task", task_id=task_id))
        except ValueError:
            flash("Invalid estimated minutes", "error")
            return redirect(url_for("views.edit_task", task_id=task_id))

    try:
        response = _call_task_api(
            "PUT",
            f"/api/tasks/{task_id}",
            json={
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "due_date": due_date.isoformat() if due_date else None,
                "estimated_minutes": estimated_minutes,
            },
        )
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))

    if response.status_code == 200:
        flash("Task updated successfully", "success")
        return redirect(url_for("views.view_task", task_id=task_id))
    if response.status_code == 400:
        flash(_response_error_message(response, "Invalid task data"), "error")
        return redirect(url_for("views.edit_task", task_id=task_id))
    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("views.login"))
    if response.status_code == 404:
        abort(404)

    flash("Error updating task. Please try again.", "error")
    return redirect(url_for("views.edit_task", task_id=task_id))


@views_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    """
    Handle task deletion.

    Sends a DELETE request to the task service for the given task.  On
    success the user is redirected to the task list with a confirmation
    flash message.

    Args:
        task_id: The primary-key ID of the task to delete.

    Returns:
        A redirect to the index page on success, or with a flash
        message on service error.  Aborts with 404 if the task does
        not exist.
    """
    try:
        response = _call_task_api("DELETE", f"/api/tasks/{task_id}")
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.index"))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.index"))

    if response.status_code == 200:
        flash("Task deleted successfully", "success")
        return redirect(url_for("views.index"))
    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("views.login"))
    if response.status_code == 404:
        abort(404)

    flash("Error deleting task. Please try again.", "error")
    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id: int):
    """
    Handle a quick status update from the task list or detail pages.

    Validates the submitted status value against the ``TaskStatus`` enum
    and sends a PATCH request to the task service's
    ``/api/tasks/<id>/status`` endpoint.  This lightweight endpoint
    allows users to transition task status without opening the full edit
    form.

    Args:
        task_id: The primary-key ID of the task to update.

    Returns:
        A redirect to the index page with a flash message indicating
        success or failure.
    """
    new_status = request.form.get("status")
    if new_status not in [status.value for status in TaskStatus]:
        flash("Invalid status", "error")
        return redirect(url_for("views.index"))

    try:
        response = _call_task_api(
            "PATCH",
            f"/api/tasks/{task_id}/status",
            json={"status": new_status},
        )
    except requests.Timeout:
        flash("Task service timed out. Please try again.", "error")
        return redirect(url_for("views.index"))
    except requests.RequestException:
        flash("Task service unavailable. Please try again later.", "error")
        return redirect(url_for("views.index"))

    if response.status_code == 200:
        flash(f"Status updated to {new_status}", "success")
        return redirect(url_for("views.index"))
    if response.status_code == 400:
        flash(_response_error_message(response, "Invalid status"), "error")
        return redirect(url_for("views.index"))
    if response.status_code == 401:
        session.pop("auth_token", None)
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("views.login"))
    if response.status_code == 404:
        abort(404)

    flash("Error updating status. Please try again.", "error")
    return redirect(url_for("views.index"))
