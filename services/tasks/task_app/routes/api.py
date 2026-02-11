"""REST API endpoints for task service."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import select

from task_app import db
from task_app.auth import require_auth
from task_app.models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

api_bp = Blueprint("task_api", __name__)


def validate_task_data(
    data: dict, required_fields: list[str] | None = None
) -> tuple[bool, str | None]:
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
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_due_date(date_string: str | None) -> datetime | None:
    if not date_string:
        return None
    parsed = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    return ensure_utc(parsed)


def _user_task_query() -> select:
    return select(Task).where(Task.user_id == g.user_id)


@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
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
    logger.info("GET /api/tasks - Fetching tasks for user_id=%s", g.user_id)

    stmt = _user_task_query()

    status = request.args.get("status")
    if status:
        stmt = stmt.where(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        stmt = stmt.where(Task.priority == priority)

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
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task.to_dict()), 200


@api_bp.route("/tasks", methods=["POST"])
@require_auth
def create_task() -> tuple[Response, int]:
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
    task = db.session.scalar(_user_task_query().where(Task.id == task_id))
    if not task:
        return jsonify({"error": "Task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted successfully"}), 200


@api_bp.route("/tasks/<int:task_id>/status", methods=["PATCH"])
@require_auth
def update_task_status(task_id: int) -> tuple[Response, int]:
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


@api_bp.errorhandler(400)
def bad_request(_: Exception) -> tuple[Response, int]:
    return jsonify({"error": "Bad request"}), 400


@api_bp.errorhandler(404)
def not_found(_: Exception) -> tuple[Response, int]:
    return jsonify({"error": "Resource not found"}), 404


@api_bp.errorhandler(500)
def internal_error(error: Exception) -> tuple[Response, int]:
    logger.error("Internal server error: %s", error)
    return jsonify({"error": "Internal server error"}), 500

