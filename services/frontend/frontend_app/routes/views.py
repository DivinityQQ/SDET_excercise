"""
HTML view routes for the frontend BFF service.

This module serves server-rendered pages and orchestrates auth/task API calls.
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


def _auth_service_url(path: str) -> str:
    """Build a full URL to an auth service endpoint."""
    return f"{current_app.config['AUTH_SERVICE_URL'].rstrip('/')}/{path.lstrip('/')}"


def _task_service_url(path: str) -> str:
    """Build a full URL to a task service endpoint."""
    return f"{current_app.config['TASK_SERVICE_URL'].rstrip('/')}/{path.lstrip('/')}"


def _verify_session_token() -> dict[str, Any] | None:
    """Verify the JWT stored in the Flask session cookie."""
    token = session.get("auth_token")
    if not token:
        return None
    return verify_token(token, current_app.config["JWT_PUBLIC_KEY"], algorithms=["RS256"])


def _task_service_headers() -> dict[str, str]:
    """Build headers for calls to the task service API."""
    token = session.get("auth_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _call_task_api(method: str, path: str, **kwargs) -> requests.Response:
    """Call task service API with per-service timeout and auth header."""
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
    """Parse ISO-8601 datetime strings returned by the task API."""
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return None


def _deserialize_task(data: dict[str, Any]) -> dict[str, Any]:
    """Convert API task payload into a template-friendly dictionary."""
    task = dict(data)
    task["due_date"] = _parse_iso_datetime(task.get("due_date"))
    task["created_at"] = _parse_iso_datetime(task.get("created_at"))
    task["updated_at"] = _parse_iso_datetime(task.get("updated_at"))
    return task


def _response_error_message(response: requests.Response, default: str) -> str:
    """Extract an error message from a JSON API response if possible."""
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
    """Render index page with standard context."""
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
    """Normalize a datetime value to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def login_required(view_func):
    """
    Decorator that requires a valid JWT in session for view routes.

    Unauthenticated users are redirected to /login.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        payload = _verify_session_token()
        if payload is None:
            session.pop("auth_token", None)
            return redirect(url_for("views.login"))

        g.user_id = payload["user_id"]
        g.username = payload["username"]
        return view_func(*args, **kwargs)

    return wrapper


@views_bp.route("/health", methods=["GET"])
def health_check():
    """Health endpoint for container probes."""
    return {"status": "healthy", "service": "frontend"}, 200


@views_bp.route("/login", methods=["GET"])
def login():
    """Render login page."""
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("login.html")


@views_bp.route("/login", methods=["POST"])
def login_submit():
    """Handle login form submission."""
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
    """Render registration page."""
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("register.html")


@views_bp.route("/register", methods=["POST"])
def register_submit():
    """Handle registration form submission."""
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
    """Clear session token and redirect to login."""
    session.pop("auth_token", None)
    flash("Logged out. Session cleared.", "success")
    return redirect(url_for("views.login"))


@views_bp.route("/")
@login_required
def index():
    """Render task list page with optional filters."""
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
    """Render empty task creation form."""
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
    """Handle task creation form submission."""
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
    Fetch a task from the task API for the current user.

    Returns:
        Parsed task dictionary on success, None when not found.
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
    """Render task detail page."""
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
        # If session expired, _get_task already handled redirect intent via flash.
        if session.get("auth_token") is None:
            return redirect(url_for("views.login"))
        abort(404)

    return render_template("task_detail.html", task=task, statuses=TaskStatus)


@views_bp.route("/tasks/<int:task_id>/edit")
@login_required
def edit_task(task_id: int):
    """Render task edit form."""
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
    """Handle task edit form submission."""
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
    """Handle task deletion."""
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
    """Handle quick status update from task list/detail pages."""
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
