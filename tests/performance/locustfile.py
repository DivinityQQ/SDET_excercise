# ruff: noqa: E402
"""Locust entrypoint for performance tests.

Examples:
- `--tags mixed` to run only mixed workload users
- `--tags auth` to run auth-focused scenarios
- omit tags to run all defined user classes
"""

from __future__ import annotations

import sys
from pathlib import Path

from locust import events

# Ensure project-root imports resolve when Locust executes from arbitrary cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.performance.scenarios.auth_storm import AuthStormUser
from tests.performance.scenarios.mixed import MixedTrafficUser
from tests.performance.scenarios.task_crud import TaskCrudUser

__all__ = ["AuthStormUser", "TaskCrudUser", "MixedTrafficUser"]

TAG_TO_USER_CLASS = {
    "auth": AuthStormUser,
    "crud": TaskCrudUser,
    "mixed": MixedTrafficUser,
}


@events.init.add_listener
def _filter_user_classes_by_tag(environment, **_kwargs):
    """Select user classes explicitly so --tags does not spawn empty classes."""
    selected_tags = set(environment.parsed_options.tags or [])
    if not selected_tags:
        return

    selected_classes = [
        user_class
        for tag, user_class in TAG_TO_USER_CLASS.items()
        if tag in selected_tags
    ]
    if selected_classes:
        environment.user_classes = selected_classes
