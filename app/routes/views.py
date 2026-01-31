"""
HTML view routes for the Task Manager web interface.

This module provides routes that render HTML templates for the
web-based user interface. These routes work alongside the API
to provide a complete user experience.

Routes:
    GET  /              - Task list page (home)
    GET  /tasks/new     - New task form
    GET  /tasks/<id>    - Task detail page
    GET  /tasks/<id>/edit - Edit task form
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from sqlalchemy import select

from app import db
from app.models import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


def get_task_or_404(task_id: int) -> Task:
    """Fetch task by ID or raise 404."""
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    return task


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@views_bp.route("/")
def index():
    """
    Render the task list page.

    Query Parameters:
        status: Filter by status
        priority: Filter by priority

    Returns:
        Rendered index.html template with task list.
    """
    logger.info("GET / - Rendering task list")

    # Get filter parameters
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    # Build statement with filters
    stmt = select(Task)

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
        current_priority=priority_filter
    )


@views_bp.route("/tasks/new")
def new_task():
    """
    Render the new task form.

    Returns:
        Rendered task_form.html template for creating a new task.
    """
    logger.info("GET /tasks/new - Rendering new task form")

    return render_template(
        "task_form.html",
        task=None,
        statuses=TaskStatus,
        priorities=TaskPriority,
        form_action=url_for("views.create_task"),
        form_title="Create New Task"
    )


@views_bp.route("/tasks", methods=["POST"])
def create_task():
    """
    Handle new task form submission.

    Form Data:
        title: Task title (required)
        description: Task description
        status: Task status
        priority: Task priority
        due_date: Due date

    Returns:
        Redirect to index on success, or back to form on error.
    """
    logger.info("POST /tasks - Creating task from form")

    title = request.form.get("title", "").strip()

    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.new_task"))

    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.new_task"))

    # Parse due date if provided
    due_date = None
    due_date_str = request.form.get("due_date")
    if due_date_str:
        try:
            due_date = ensure_utc(datetime.fromisoformat(due_date_str))
        except ValueError:
            flash("Invalid date format", "error")
            return redirect(url_for("views.new_task"))

    task = Task(
        title=title,
        description=request.form.get("description", "").strip(),
        status=request.form.get("status", TaskStatus.PENDING.value),
        priority=request.form.get("priority", TaskPriority.MEDIUM.value),
        due_date=due_date
    )

    db.session.add(task)
    db.session.commit()

    flash("Task created successfully", "success")
    logger.info(f"Created task {task.id} from form")

    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>")
def view_task(task_id: int):
    """
    Render the task detail page.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        Rendered task_detail.html template, or 404 if not found.
    """
    logger.info(f"GET /tasks/{task_id} - Viewing task")

    task = get_task_or_404(task_id)

    return render_template(
        "task_detail.html",
        task=task,
        statuses=TaskStatus
    )


@views_bp.route("/tasks/<int:task_id>/edit")
def edit_task(task_id: int):
    """
    Render the edit task form.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        Rendered task_form.html template for editing, or 404 if not found.
    """
    logger.info(f"GET /tasks/{task_id}/edit - Rendering edit form")

    task = get_task_or_404(task_id)

    return render_template(
        "task_form.html",
        task=task,
        statuses=TaskStatus,
        priorities=TaskPriority,
        form_action=url_for("views.update_task", task_id=task_id),
        form_title="Edit Task"
    )


@views_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
def update_task(task_id: int):
    """
    Handle edit task form submission.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        Redirect to task detail on success, or back to form on error.
    """
    logger.info(f"POST /tasks/{task_id}/update - Updating task from form")

    task = get_task_or_404(task_id)

    title = request.form.get("title", "").strip()

    if not title:
        flash("Title is required", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))

    if len(title) > 200:
        flash("Title must be 200 characters or less", "error")
        return redirect(url_for("views.edit_task", task_id=task_id))

    # Parse due date if provided
    due_date = None
    due_date_str = request.form.get("due_date")
    if due_date_str:
        try:
            due_date = ensure_utc(datetime.fromisoformat(due_date_str))
        except ValueError:
            flash("Invalid date format", "error")
            return redirect(url_for("views.edit_task", task_id=task_id))

    task.title = title
    task.description = request.form.get("description", "").strip()
    task.status = request.form.get("status", task.status)
    task.priority = request.form.get("priority", task.priority)
    task.due_date = due_date

    db.session.commit()

    flash("Task updated successfully", "success")
    logger.info(f"Updated task {task_id} from form")

    return redirect(url_for("views.view_task", task_id=task_id))


@views_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id: int):
    """
    Handle task deletion.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        Redirect to index after deletion.
    """
    logger.info(f"POST /tasks/{task_id}/delete - Deleting task")

    task = get_task_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted successfully", "success")
    logger.info(f"Deleted task {task_id}")

    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
def update_status(task_id: int):
    """
    Handle quick status update from the task list.

    Args:
        task_id: The unique identifier of the task.

    Form Data:
        status: New status value

    Returns:
        Redirect back to index.
    """
    logger.info(f"POST /tasks/{task_id}/status - Quick status update")

    task = get_task_or_404(task_id)

    new_status = request.form.get("status")
    if new_status in [s.value for s in TaskStatus]:
        task.status = new_status
        db.session.commit()
        flash(f"Status updated to {new_status}", "success")
    else:
        flash("Invalid status", "error")

    return redirect(url_for("views.index"))
