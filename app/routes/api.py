"""
REST API endpoints for Task management.

This module provides CRUD operations for tasks via HTTP methods.
All endpoints return JSON responses and follow REST conventions.

Endpoints:
    GET    /api/health        - Health check
    GET    /api/tasks          - List all tasks (with optional filtering)
    GET    /api/tasks/<id>     - Get a single task by ID
    POST   /api/tasks          - Create a new task
    PUT    /api/tasks/<id>     - Update an existing task
    DELETE /api/tasks/<id>     - Delete a task
    PATCH  /api/tasks/<id>/status - Update task status only
"""

import logging
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, Response
from sqlalchemy import select

from app import db
from app.models import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def validate_task_data(data: dict, required_fields: list[str] | None = None) -> tuple[bool, str | None]:
    """
    Validate task data from request.

    Args:
        data: Dictionary containing task data.
        required_fields: List of fields that must be present.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if required_fields:
        for field in required_fields:
            value = data.get(field)
            # Check if field exists and has non-whitespace content
            if not value or (isinstance(value, str) and not value.strip()):
                return False, f"'{field}' is required"

    # Validate status if provided
    if "status" in data:
        valid_statuses = [s.value for s in TaskStatus]
        if data["status"] not in valid_statuses:
            return False, f"Invalid status. Must be one of: {valid_statuses}"

    # Validate priority if provided
    if "priority" in data:
        valid_priorities = [p.value for p in TaskPriority]
        if data["priority"] not in valid_priorities:
            return False, f"Invalid priority. Must be one of: {valid_priorities}"

    # Validate title length if provided
    if "title" in data and data["title"]:
        if len(data["title"]) > 200:
            return False, "Title must be 200 characters or less"

    # Validate due_date format if provided
    if "due_date" in data and data["due_date"]:
        try:
            datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False, "Invalid due_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"

    # Validate estimated_minutes if provided
    if "estimated_minutes" in data and data["estimated_minutes"] is not None:
        if not isinstance(data["estimated_minutes"], int) or data["estimated_minutes"] < 1:
            return False, "estimated_minutes must be a positive integer"

    return True, None


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_due_date(date_string: str | None) -> datetime | None:
    """
    Parse due date string to datetime object.

    Args:
        date_string: ISO format date string or None.

    Returns:
        datetime object or None.
    """
    if not date_string:
        return None
    parsed = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    return ensure_utc(parsed)


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """Health check endpoint for deployment verification."""
    return jsonify({
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "version": os.getenv("APP_VERSION", "unknown")
    }), 200


@api_bp.route("/tasks", methods=["GET"])
def get_tasks() -> tuple[Response, int]:
    """
    List all tasks with optional filtering and sorting.

    Query Parameters:
        status: Filter by status (pending, in_progress, completed)
        priority: Filter by priority (low, medium, high)
        sort: Sort field (created_at, due_date, priority, title)
        order: Sort order (asc, desc)

    Returns:
        JSON response with list of tasks and 200 status code.
    """
    logger.info("GET /api/tasks - Fetching all tasks")

    # Start with base statement
    stmt = select(Task)

    # Apply filters
    status = request.args.get("status")
    if status:
        stmt = stmt.where(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        stmt = stmt.where(Task.priority == priority)

    # Apply sorting
    sort_field = request.args.get("sort", "created_at")
    sort_order = request.args.get("order", "desc")

    if hasattr(Task, sort_field):
        column = getattr(Task, sort_field)
        if sort_order == "desc":
            stmt = stmt.order_by(column.desc())
        else:
            stmt = stmt.order_by(column.asc())

    tasks = db.session.scalars(stmt).all()
    logger.info(f"Found {len(tasks)} tasks")

    return jsonify({
        "tasks": [task.to_dict() for task in tasks],
        "count": len(tasks)
    }), 200


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id: int) -> tuple[Response, int]:
    """
    Get a single task by ID.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        JSON response with task data and 200 status code,
        or error message and 404 if not found.
    """
    logger.info(f"GET /api/tasks/{task_id} - Fetching task")

    task = db.session.get(Task, task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task.to_dict()), 200


@api_bp.route("/tasks", methods=["POST"])
def create_task() -> tuple[Response, int]:
    """
    Create a new task.

    Request Body (JSON):
        title: Task title (required)
        description: Task description (optional)
        status: Task status (optional, default: pending)
        priority: Task priority (optional, default: medium)
        due_date: Due date in ISO format (optional)
        estimated_minutes: Estimated duration in minutes (optional, positive integer)

    Returns:
        JSON response with created task and 201 status code,
        or error message and 400 if validation fails.
    """
    logger.info("POST /api/tasks - Creating new task")

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # Validate required fields
    is_valid, error = validate_task_data(data, required_fields=["title"])
    if not is_valid:
        logger.warning(f"Validation failed: {error}")
        return jsonify({"error": error}), 400

    # Create new task
    task = Task(
        title=data["title"],
        description=data.get("description"),
        status=data.get("status", TaskStatus.PENDING.value),
        priority=data.get("priority", TaskPriority.MEDIUM.value),
        due_date=parse_due_date(data.get("due_date")),
        estimated_minutes=data.get("estimated_minutes")
    )

    db.session.add(task)
    db.session.commit()

    logger.info(f"Created task with ID: {task.id}")
    return jsonify(task.to_dict()), 201


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id: int) -> tuple[Response, int]:
    """
    Update an existing task.

    Args:
        task_id: The unique identifier of the task.

    Request Body (JSON):
        title: Task title
        description: Task description
        status: Task status
        priority: Task priority
        due_date: Due date in ISO format
        estimated_minutes: Estimated duration in minutes (positive integer)

    Returns:
        JSON response with updated task and 200 status code,
        or error message and 404/400 if not found or validation fails.
    """
    logger.info(f"PUT /api/tasks/{task_id} - Updating task")

    task = db.session.get(Task, task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # Validate data
    is_valid, error = validate_task_data(data)
    if not is_valid:
        logger.warning(f"Validation failed: {error}")
        return jsonify({"error": error}), 400

    # Update fields if provided
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

    logger.info(f"Updated task {task_id}")
    return jsonify(task.to_dict()), 200


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int) -> tuple[Response, int]:
    """
    Delete a task.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        JSON response with success message and 200 status code,
        or error message and 404 if not found.
    """
    logger.info(f"DELETE /api/tasks/{task_id} - Deleting task")

    task = db.session.get(Task, task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        return jsonify({"error": "Task not found"}), 404

    db.session.delete(task)
    db.session.commit()

    logger.info(f"Deleted task {task_id}")
    return jsonify({"message": "Task deleted successfully"}), 200


@api_bp.route("/tasks/<int:task_id>/status", methods=["PATCH"])
def update_task_status(task_id: int) -> tuple[Response, int]:
    """
    Update only the status of a task.

    This is a convenience endpoint for quick status updates
    without sending the full task data.

    Args:
        task_id: The unique identifier of the task.

    Request Body (JSON):
        status: New status (pending, in_progress, completed)

    Returns:
        JSON response with updated task and 200 status code,
        or error message and 404/400 if not found or validation fails.
    """
    logger.info(f"PATCH /api/tasks/{task_id}/status - Updating status")

    task = db.session.get(Task, task_id)
    if not task:
        logger.warning(f"Task {task_id} not found")
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "'status' field is required"}), 400

    # Validate status
    valid_statuses = [s.value for s in TaskStatus]
    if data["status"] not in valid_statuses:
        return jsonify({
            "error": f"Invalid status. Must be one of: {valid_statuses}"
        }), 400

    task.status = data["status"]
    db.session.commit()

    logger.info(f"Updated task {task_id} status to {data['status']}")
    return jsonify(task.to_dict()), 200


# -----------------------------------------------------------------------------
# Error Handlers
# -----------------------------------------------------------------------------

@api_bp.errorhandler(400)
def bad_request(error: Exception) -> tuple[Response, int]:
    """Handle 400 Bad Request errors."""
    return jsonify({"error": "Bad request"}), 400


@api_bp.errorhandler(404)
def not_found(error: Exception) -> tuple[Response, int]:
    """Handle 404 Not Found errors."""
    return jsonify({"error": "Resource not found"}), 404


@api_bp.errorhandler(500)
def internal_error(error: Exception) -> tuple[Response, int]:
    """Handle 500 Internal Server errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500
