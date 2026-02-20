# ruff: noqa: E402
"""
Locust entrypoint for performance tests.

This is the file that the ``locust`` CLI discovers and loads.  It
imports every concrete user class and wires up a custom ``init`` event
listener that maps ``--tags`` values to user classes, ensuring Locust
only spawns the classes the operator actually requested.

Usage examples::

    # Run all scenarios (auth, crud, and mixed users together):
    locust -f tests/performance/locustfile.py --host http://localhost:5000

    # Run only the production-like mixed workload:
    locust -f tests/performance/locustfile.py --tags mixed ...

    # Run only auth-focused stress testing:
    locust -f tests/performance/locustfile.py --tags auth ...

Key Concepts Demonstrated:
- Locust ``events.init`` hook for dynamic user-class filtering
- Clean separation between the entrypoint (this file) and scenario
  definitions (the ``scenarios`` sub-package)
- ``sys.path`` manipulation so imports resolve regardless of the
  working directory Locust is launched from
"""

from __future__ import annotations

import sys
from pathlib import Path

from locust import events

# Locust may be invoked from any directory (project root, repo parent,
# CI workspace, etc.).  Inserting the project root onto ``sys.path``
# guarantees that ``from tests.performance.…`` imports always resolve.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.performance.scenarios.auth_storm import AuthStormUser
from tests.performance.scenarios.mixed import MixedTrafficUser
from tests.performance.scenarios.task_crud import TaskCrudUser

__all__ = ["AuthStormUser", "TaskCrudUser", "MixedTrafficUser"]

# Maps CLI ``--tags`` values to concrete user classes.  When no tags
# are provided Locust spawns all classes in ``__all__``; when tags *are*
# provided the ``init`` listener below narrows the set.
TAG_TO_USER_CLASS = {
    "auth": AuthStormUser,
    "crud": TaskCrudUser,
    "mixed": MixedTrafficUser,
}


@events.init.add_listener
def _filter_user_classes_by_tag(environment, **_kwargs):
    """
    Select user classes explicitly so ``--tags`` does not spawn empty classes.

    Locust's built-in tag filtering hides individual ``@task`` methods
    but still instantiates every user class.  For scenarios where each
    class represents a distinct workload profile, this listener replaces
    ``environment.user_classes`` entirely so that only the requested
    profiles are spawned.
    """
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
