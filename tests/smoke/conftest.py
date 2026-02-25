"""
Smoke-test fixtures for the microservices stack.

Provides the ``smoke_base_url`` session-scoped fixture that yields a healthy
gateway URL shared across the entire smoke suite.  URL resolution is delegated
to :func:`shared.live_stack.live_stack_url`, which reuses an already-running
local stack when one is healthy or starts a docker compose stack on demand.

Key SDET Concepts Demonstrated:
- Session-scoped URL fixtures to share a single live stack across all smoke tests
- Delegating stack lifecycle management to a shared helper for DRY reuse across suites
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

try:
    from shared.live_stack import live_stack_url
except ModuleNotFoundError:  # pragma: no cover - fallback for pytest script entrypoints
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    from shared.live_stack import live_stack_url


@pytest.fixture(scope="session")
def smoke_base_url() -> Generator[str, None, None]:
    """Yield a healthy gateway URL for smoke tests."""
    run_id = uuid.uuid4().hex[:8]
    yield from live_stack_url(
        base_url_env="TEST_BASE_URL",
        compose_project_env="SMOKE_COMPOSE_PROJECT",
        compose_file_env="SMOKE_COMPOSE_FILE",
        compose_project_default=f"taskapp-smoke-{run_id}",
        suite_name="smoke",
    )
