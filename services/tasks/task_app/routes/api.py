"""
REST API Endpoints for the Task Service.

Exposes a full CRUD interface for tasks, plus a health-check endpoint.
Every task-mutating endpoint is protected by JWT authentication (via the
``require_auth`` decorator), and all queries are automatically scoped to
the authenticated user to enforce tenant isolation.

Endpoints:
    GET    /api/health                  - Service health check (public)
    GET    /api/tasks                   - List tasks (with optional filters)
    GET    /api/tasks/<id>              - Retrieve a single task
    POST   /api/tasks                   - Create a new task
    PUT    /api/tasks/<id>              - Full update of a task
    DELETE /api/tasks/<id>              - Delete a task
    PATCH  /api/tasks/<id>/status       - Update only the task status

Key Concepts Demonstrated:
- RESTful CRUD with Flask blueprints
- Query-string filtering and dynamic sort/order
- Tenant isolation via JWT-derived ``user_id``
- Input validation helpers extracted from route handlers
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import select

from .. import db
from ..auth import require_auth
from ..models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

api_bp = Blueprint("task_api", __name__)


# =====================================================================
# Helper Functions
# =====================================================================


def validate_task_data(
    data: dict, required_fields: list[str] | None = None
) -> tuple[bool, str | None]:
    """
    Validate incoming task payload against business rules.

    Checks required fields, enum membership for status/priority, title
    length, ISO-8601 conformance for ``due_date``, and positivity for
    ``estimated_minutes``.

    Args:
        data: The deserialised JSON request body.
        required_fields: Optional list of field names that must be present
            and non-empty.

    Returns:
        A two-element tuple ``(is_valid, error_message)``.  When valid,
        ``error_message`` is ``None``.
    """
    if required_fields:
        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                return False, f"'{field}' is required"

    if "status" in data:
        valid_statuses = [s.value for s in TaskStatus]
        if data["status"] not in valid_statuses:
            return False, f"Invalid status. Must be one of: {valid_statuses}"

    if "priority" in data:
        valid_priorities = [p.value for p in TaskPriority]
        if data["priority"] not in valid_priorities:
            return False, f"Invalid priority. Must be one of: {valid_priorities}"

    if "title" in data and data["title"]:
        if len(data["title"]) > 200:
            return False, "Title must be 200 characters or less"

    if "due_date" in data and data["due_date"]:
        try:
            datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return (
                False,
                "Invalid due_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
            )

    if "estimated_minutes" in data and data["estimated_minutes"] is not None:
        if (
            not isinstance(data["estimated_minutes"], int)
            or data["estimated_minutes"] < 1
        ):
            return False, "estimated_minutes must be a positive integer"

    return True, None


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


def parse_due_date(date_string: str | None) -> datetime | None:
    """
    Parse an optional ISO-8601 date string into a UTC datetime.

    Args:
        date_string: An ISO-8601 formatted string, or ``None``.

    Returns:
        A timezone-aware UTC datetime, or ``None`` if the input was
        ``None`` or empty.
    """
    if not date_string:
        return None
    parsed = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    return ensure_utc(parsed)


def _user_task_query() -> select:
    """
    Build a base SQLAlchemy ``select`` scoped to the authenticated user.

    Filters ``Task.user_id`` by ``g.user_id`` (set by ``require_auth``),
    so every downstream query automatically enforces tenant isolation --
    a user can never retrieve or modify another user's tasks.

    Returns:
        A SQLAlchemy ``Select`` statement pre-filtered to the current
        user's tasks.
    """
    # Tenant isolation: only return rows belonging to the JWT-authenticated user.
    return select(Task).where(Task.user_id == g.user_id)


# =====================================================================
# API Endpoints
# =====================================================================


@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """
    Return service health status.

    This endpoint is public (no authentication required) and is intended
    for load-balancer and orchestrator liveness probes.

    Returns:
        JSON object with service name, status, and environment.
    """
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "tasks",
                "environment": os.getenv("ENVIRONMENT", "unknown"),
            }
        ),
        200,
    )


@api_bp.route("/tasks", methods=["GET"])
@require_auth
def get_tasks() -> tuple[Response, int]:
    """
    List all tasks for the authenticated user.

    Supports optional query-string filters (``status``, ``priority``)
    and sorting (``sort`` field name, ``order`` asc/desc).

    Returns:
        JSON object with a ``tasks`` array and a ``count`` of results.
    """
    logger.info("GET /api/tasks - Fetching tasks for user_id=%s", g.user_id)

    stmt = _user_task_query()

    # Optional query-string filters -- narrow results without extra endpoints.
    status = request.args.get("status")
    if status:
        stmt = stmt.where(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        stmt = stmt.where(Task.priority == priority)

    # Dynamic sort: the client can choose any valid Task column and order.
    # Defaults to newest-first (created_at desc) when no parameters given.
    sort_field = request.args.get("sort", "created_at")
    sort_order = request.args.get("order", "desc")
    if hasattr(Task, sort_field):
        column = getattr(Task, sort_field)
        if sort_order == "desc":
            stmt = stmt.order_by(column.desc())
        else:
            stmt = stmt.order_by(column.asc())

    tasks = db.session.scalars(stmt).all()
    return jsonify({"tasks": [task.to_dict() for task in tasks], "count": len(tasks)}), 200


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id: int) -> tuple[Response, int]:
    """
    Retrieve a single task by ID for the authenticated user.

    Args:
        task_id: The primary-key ID of the task to retrieve.

    Returns:
        JSON representation of the task, or a 404 error if not found
        (or not owned by the current user).
    """
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task.to_dict()), 200


@api_bp.route("/tasks", methods=["POST"])
@require_auth
def create_task() -> tuple[Response, int]:
    """
    Create a new task for the authenticated user.

    Expects a JSON body with at least a ``title`` field.  Optional fields
    include ``description``, ``status``, ``priority``, ``due_date``, and
    ``estimated_minutes``.

    Returns:
        JSON representation of the newly created task with a 201 status.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    is_valid, error = validate_task_data(data, required_fields=["title"])
    if not is_valid:
        return jsonify({"error": error}), 400

    task = Task(
        user_id=g.user_id,
        title=data["title"],
        description=data.get("description"),
        status=data.get("status", TaskStatus.PENDING.value),
        priority=data.get("priority", TaskPriority.MEDIUM.value),
        due_date=parse_due_date(data.get("due_date")),
        estimated_minutes=data.get("estimated_minutes"),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id: int) -> tuple[Response, int]:
    """
    Full update of an existing task.

    Only the fields present in the JSON body are modified (partial update
    semantics despite using PUT).  The task must belong to the authenticated
    user.

    Args:
        task_id: The primary-key ID of the task to update.

    Returns:
        JSON representation of the updated task, or 404 if not found.
    """
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    is_valid, error = validate_task_data(data)
    if not is_valid:
        return jsonify({"error": error}), 400

    if "title" in data:
        task.title = data["title"]
    if "description" in data:
        task.description = data["description"]
    if "status" in data:
        task.status = data["status"]
    if "priority" in data:
        task.priority = data["priority"]
    if "due_date" in data:
        task.due_date = parse_due_date(data["due_date"])
    if "estimated_minutes" in data:
        task.estimated_minutes = data["estimated_minutes"]

    db.session.commit()
    return jsonify(task.to_dict()), 200


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id: int) -> tuple[Response, int]:
    """
    Delete a task by ID.

    The task must belong to the authenticated user.

    Args:
        task_id: The primary-key ID of the task to delete.

    Returns:
        JSON confirmation message, or 404 if not found.
    """
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted successfully"}), 200


@api_bp.route("/tasks/<int:task_id>/status", methods=["PATCH"])
@require_auth
def update_task_status(task_id: int) -> tuple[Response, int]:
    """
    Update only the status of a task.

    Provides a lightweight PATCH endpoint so clients can transition a
    task's status without sending the full resource representation.

    Args:
        task_id: The primary-key ID of the task to update.

    Returns:
        JSON representation of the updated task, or 404/400 on error.
    """
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "'status' field is required"}), 400

    valid_statuses = [s.value for s in TaskStatus]
    if data["status"] not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    task.status = data["status"]
    db.session.commit()
    return jsonify(task.to_dict()), 200


# =====================================================================
# Error Handlers
# =====================================================================


@api_bp.errorhandler(400)
def bad_request(_: Exception) -> tuple[Response, int]:
    """Return a JSON 400 Bad Request error."""
    return jsonify({"error": "Bad request"}), 400


@api_bp.errorhandler(404)
def not_found(_: Exception) -> tuple[Response, int]:
    """Return a JSON 404 Not Found error."""
    return jsonify({"error": "Resource not found"}), 404


@api_bp.errorhandler(500)
def internal_error(error: Exception) -> tuple[Response, int]:
    """Log the exception and return a JSON 500 Internal Server Error."""
    logger.error("Internal server error: %s", error)
    return jsonify({"error": "Internal server error"}), 500
