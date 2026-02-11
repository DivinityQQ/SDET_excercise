"""HTML view routes for task service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select

from .. import db
from ..models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


def _current_user_id() -> int:
    """Temporary local user identity for pre-auth view compatibility."""
    return int(session.get("user_id", 1))


def get_task_or_404(task_id: int) -> Task:
    task = db.session.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == _current_user_id())
    )
    if not task:
        abort(404)
    return task


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@views_bp.route("/")
def index():
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    stmt = select(Task).where(Task.user_id == _current_user_id())
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
    )


@views_bp.route("/tasks/new")
def new_task():
    return render_template(
        "task_form.html",
        task=None,
        statuses=TaskStatus,
        priorities=TaskPriority,
        form_action=url_for("views.create_task"),
        form_title="Create New Task",
    )


@views_bp.route("/tasks", methods=["POST"])
def create_task():
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
        user_id=_current_user_id(),
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
def view_task(task_id: int):
    task = get_task_or_404(task_id)
    return render_template("task_detail.html", task=task, statuses=TaskStatus)


@views_bp.route("/tasks/<int:task_id>/edit")
def edit_task(task_id: int):
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
def update_task(task_id: int):
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
def delete_task(task_id: int):
    task = get_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted successfully", "success")
    return redirect(url_for("views.index"))


@views_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
def update_status(task_id: int):
    task = get_task_or_404(task_id)
    new_status = request.form.get("status")
    if new_status in [s.value for s in TaskStatus]:
        task.status = new_status
        db.session.commit()
        flash(f"Status updated to {new_status}", "success")
    else:
        flash("Invalid status", "error")
    return redirect(url_for("views.index"))
