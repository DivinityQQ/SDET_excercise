"""
HTML View Routes for the Task Service Web UI.

Serves server-rendered HTML pages (login, registration, task list, task
detail, create/edit forms) and processes form submissions.  Authentication
is delegated to the **auth service** via cross-service HTTP calls --
this module never accesses a user/password database directly.

Tokens received from the auth service are stored in the Flask session
cookie so that subsequent page loads can re-verify the user without
requiring them to re-authenticate on every request.

Key Concepts Demonstrated:
- Server-rendered views with Flask templates (Jinja2)
- Cross-service HTTP calls (``requests`` library) to the auth service
- Session-based token storage for browser authentication flows
- Decorator pattern (``login_required``) for protecting view routes
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
from sqlalchemy import select

from .. import db
from ..auth import verify_token
from ..models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


def _auth_service_url(path: str) -> str:
    """
    Build a full URL to an auth service endpoint.

    Reads the base URL from ``AUTH_SERVICE_URL`` in the app config and
    appends the given *path*, ensuring there are no doubled slashes.

    Args:
        path: The path component of the auth endpoint
            (e.g., ``"/api/auth/login"``).

    Returns:
        The fully-qualified URL string.
    """
    return f"{current_app.config['AUTH_SERVICE_URL'].rstrip('/')}/{path.lstrip('/')}"


def _verify_session_token() -> dict[str, Any] | None:
    """
    Verify the JWT stored in the Flask session cookie.

    Returns:
        The decoded token payload if valid, or ``None`` if no token is
        present or verification fails.
    """
    token = session.get("auth_token")
    if not token:
        return None
    return verify_token(token, current_app.config["JWT_PUBLIC_KEY"], algorithms=["RS256"])


def login_required(view_func):
    """
    Decorator that requires a valid JWT in the session for view routes.

    Similar in purpose to ``require_auth`` in ``auth.py``, but designed
    for browser-facing routes: instead of returning a 401 JSON error, it
    redirects unauthenticated users to the login page.  On success it
    populates ``flask.g`` with the user identity, just like the API
    decorator.

    Args:
        view_func: The Flask view function to protect.

    Returns:
        A wrapped view function that redirects to login when no valid
        session token exists.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        payload = _verify_session_token()
        if payload is None:
            # Clear any stale/invalid token before redirecting so the user
            # is not stuck in a redirect loop with a bad cookie value.
            session.pop("auth_token", None)
            return redirect(url_for("views.login"))

        # Store user identity on flask.g for downstream access by view
        # functions and templates.
        g.user_id = payload["user_id"]
        g.username = payload["username"]
        return view_func(*args, **kwargs)

    return wrapper


def get_task_or_404(task_id: int) -> Task:
    """
    Retrieve a task by ID for the current user, or abort with 404.

    Args:
        task_id: The primary-key ID of the task to look up.

    Returns:
        The ``Task`` instance if found and owned by the current user.

    Raises:
        404: If no matching task exists.
    """
    task = db.session.scalar(select(Task).where(Task.id == task_id, Task.user_id == g.user_id))
    if not task:
        abort(404)
    return task


def ensure_utc(value: datetime) -> datetime:
    """
    Normalise a datetime to UTC.

    Args:
        value: The datetime to normalise.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@views_bp.route("/login", methods=["GET"])
def login():
    """
    Render the login page.

    If the user already has a valid session token, redirect straight to
    the task list instead of showing the login form.
    """
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("login.html")


@views_bp.route("/login", methods=["POST"])
def login_submit():
    """
    Handle login form submission.

    Sends the credentials to the auth service via a cross-service HTTP
    POST.  On success, stores the returned JWT in the Flask session
    cookie so that subsequent requests are authenticated automatically.
    """
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("login.html"), 400

    # Cross-service call: delegate credential verification to the auth
    # service.  The task service never stores or checks passwords itself.
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
        # Persist the JWT in the encrypted Flask session cookie so the
        # browser does not need to re-authenticate on every page load.
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

    If the user already has a valid session, redirect to the task list.
    """
    if _verify_session_token() is not None:
        return redirect(url_for("views.index"))
    return render_template("register.html")


@views_bp.route("/register", methods=["POST"])
def register_submit():
    """
    Handle registration form submission.

    Forwards the new user's details to the auth service via a cross-service
    HTTP POST.  On success, redirects to the login page so the user can
    sign in with their new credentials.
    """
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("Username, email, and password are required.", "error")
        return render_template("register.html"), 400

    # Cross-service call: delegate account creation to the auth service.
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
        error_message = response.json().get("error", "Registration failed.")
        flash(error_message, "error")
        return render_template("register.html"), response.status_code

    flash("Unexpected registration error. Please try again.", "error")
    return render_template("register.html"), 502


@views_bp.route("/logout", methods=["POST"])
def logout():
    """
    Log the user out by clearing the session token and redirect to login.
    """
    session.pop("auth_token", None)
    flash("Logged out. Session cleared.", "success")
    return redirect(url_for("views.login"))


@views_bp.route("/")
@login_required
def index():
    """
    Render the main task list page with optional status/priority filters.

    Queries the database for all tasks belonging to the authenticated
    user, applying any query-string filters, and passes the results to
    the ``index.html`` template.
    """
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    stmt = select(Task).where(Task.user_id == g.user_id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if priority_filter:
        stmt = stmt.where(Task.priority == priority_filter)

    stmt = stmt.order_by(Task.created_at.desc())
    tasks = db.session.scalars(stmt).all()

    return render_template(
        "index.html",
        tasks=tasks,
        statuses=TaskStatus,
        priorities=TaskPriority,
        current_status=status_filter,
        current_priority=priority_filter,
        current_username=g.username,
    )


@views_bp.route("/tasks/new")
@login_required
def new_task():
    """
    Render the blank task creation form.
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
    Handle the task creation form submission.

    Validates form input, creates a new ``Task`` row owned by the
    authenticated user, and redirects to the task list on success.
    """
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.new_task"))
    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.new_task"))

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

    task = Task(
        user_id=g.user_id,
        title=title,
        description=request.form.get("description", "").strip(),
        status=request.form.get("status", TaskStatus.PENDING.value),
        priority=request.form.get("priority", TaskPriority.MEDIUM.value),
        due_date=due_date,
        estimated_minutes=estimated_minutes,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task created successfully", "success")
    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>")
@login_required
def view_task(task_id: int):
    """
    Render the detail page for a single task.

    Args:
        task_id: The primary-key ID of the task to display.
    """
    task = get_task_or_404(task_id)
    return render_template("task_detail.html", task=task, statuses=TaskStatus)


@views_bp.route("/tasks/<int:task_id>/edit")
@login_required
def edit_task(task_id: int):
    """
    Render the task edit form pre-populated with the task's current values.

    Args:
        task_id: The primary-key ID of the task to edit.
    """
    task = get_task_or_404(task_id)
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

    Validates form input and applies changes to the existing task.

    Args:
        task_id: The primary-key ID of the task to update.
    """
    task = get_task_or_404(task_id)

    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))
    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))

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

    task.title = title
    task.description = request.form.get("description", "").strip()
    task.status = request.form.get("status", task.status)
    task.priority = request.form.get("priority", task.priority)
    task.due_date = due_date
    task.estimated_minutes = estimated_minutes

    db.session.commit()
    flash("Task updated successfully", "success")
    return redirect(url_for("views.view_task", task_id=task_id))


@views_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    """
    Handle the task deletion form submission.

    Args:
        task_id: The primary-key ID of the task to delete.
    """
    task = get_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted successfully", "success")
    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id: int):
    """
    Handle the quick-status-update form submission from the task list.

    Allows the user to change a task's status directly from the list
    page without navigating to the full edit form.

    Args:
        task_id: The primary-key ID of the task to update.
    """
    task = get_task_or_404(task_id)
    new_status = request.form.get("status")
    if new_status in [status.value for status in TaskStatus]:
        task.status = new_status
        db.session.commit()
        flash(f"Status updated to {new_status}", "success")
    else:
        flash("Invalid status", "error")
    return redirect(url_for("views.index"))
