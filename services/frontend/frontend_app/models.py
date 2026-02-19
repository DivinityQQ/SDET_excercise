"""
Frontend service data models.

Defines lightweight enum types that mirror the task service's data contract.
The enums are intentionally duplicated rather than imported from the task
service so that each micro-service can be deployed, tested, and versioned
independently -- a core tenet of the micro-services architecture demonstrated
by this repository.

Both enums inherit from ``str`` as well as ``Enum`` so that their values
serialise naturally to JSON strings and can be compared directly against
plain strings returned by the task API without explicit ``.value`` access.

Key Concepts Demonstrated:
- Contract duplication for service independence
- ``str``/``Enum`` dual inheritance for ergonomic serialisation
"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    """
    Task lifecycle statuses (mirrors the task service contract).

    Used in Jinja templates to populate ``<select>`` dropdowns and to
    drive the status-filter logic on the task list page.

    Attributes:
        PENDING: Task has been created but work has not started.
        IN_PROGRESS: Task is actively being worked on.
        COMPLETED: Task has been finished.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    """
    Task priority levels (mirrors the task service contract).

    Rendered in templates as colour-coded badges and used for the
    priority-filter dropdown on the task list page.

    Attributes:
        LOW: Low urgency.
        MEDIUM: Normal urgency (default for new tasks).
        HIGH: High urgency.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
