# Baseline: Monolith Test Matrix and Timing

Captured on: 2026-02-11 16:02:24 +01:00
Commit: 34ce4b8
Branch at capture time: `feature/microservices-conversion`
Python: `Python 3.13.2`

## Command: `.\\venv\\Scripts\\python -m pytest --co -q`
Exit code: `0`

```text
collecting ... collected 96 items
========================= 96 tests collected in 0.85s =========================
```

## Command: `.\\venv\\Scripts\\python -m pytest -v --durations=0`
Exit code: `1`

```text
=========================== short test summary info ===========================
FAILED tests/smoke/test_health.py::test_app_is_running
FAILED tests/smoke/test_health.py::test_api_health
======================== 2 failed, 94 passed in 38.57s =======================
```

## Slowest Tests Snapshot

```text
4.12s call     tests/smoke/test_health.py::test_app_is_running
4.10s call     tests/e2e/test_task_flows.py::TestCompleteTaskLifecycle::test_full_task_lifecycle[chromium]
4.04s call     tests/smoke/test_health.py::test_api_health
3.04s call     tests/e2e/test_task_flows.py::TestTaskEstimatedMinutesFlow::test_edit_task_estimated_minutes[chromium]
2.93s call     tests/e2e/test_task_flows.py::TestTaskEditFlow::test_edit_task_updates_values[chromium]
```

## Notes

- Smoke failures are environment-related (`localhost:5000` not running during baseline run), not test collection issues.
- Baseline artifacts were captured before any microservices code changes.
