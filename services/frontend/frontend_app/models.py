"""
Frontend service data models.

Enums are intentionally duplicated from task service to keep runtime service
dependencies simple for this learning repository.
"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    """Task lifecycle statuses (matches task API contract)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    """Task priority levels (matches task API contract)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
