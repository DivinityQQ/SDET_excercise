# Performance Testing with Locust

This directory adds API-level load testing for regression detection.

Important: CI numbers are a regression signal, not capacity claims.

## Scenarios

| Tag | User class | Purpose |
| --- | --- | --- |
| `mixed` | `MixedTrafficUser` | Read-heavy production-like workload (70/20/10 read/write/auth) |
| `crud` | `TaskCrudUser` | Focused task CRUD pressure |
| `auth` | `AuthStormUser` | Authentication/verify traffic bursts |

All scenarios target the gateway (`http://localhost:5000`) so metrics include proxy behavior.

## Local Run (headless)

```bash
locust -f tests/performance/locustfile.py \
  --host http://localhost:5000 \
  --tags mixed \
  --headless \
  --only-summary \
  --reset-stats \
  --exit-code-on-error 0 \
  --users 5 \
  --spawn-rate 2 \
  --run-time 30s \
  --csv results/local_mixed \
  --html results/local_mixed.html
```

## Local Run (Web UI)

```bash
locust -f tests/performance/locustfile.py --host http://localhost:5000
```

Then open <http://localhost:8089>.

## Threshold Gate

```bash
python tests/performance/check_thresholds.py \
  --stats results/local_mixed_stats.csv \
  --thresholds tests/performance/thresholds.yml
```

Exit codes:
- `0`: pass
- `1`: threshold breach
- `2`: script/config error

## Notes

- Dynamic URLs are grouped with `name=...` (for example `/api/tasks/[id] [GET]`).
- `catch_response=True` is used for semantic pass/fail checks.
- Users register/login once in `on_start()`; CRUD loops do not repeatedly register.
