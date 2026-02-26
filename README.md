# SDET Exercise — Microservices Edition

A task management application used to practice SDET workflows in a microservices architecture.

## Architecture

```
                     ┌──────────────┐
   Client ────────►  │   Gateway    │  :5000
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │   Frontend   │ :5030
                     │   Service    │
                     └──────┬───────┘
                    ┌───────┴────────┐
                    │                │
              ┌─────▼────┐     ┌─────▼────┐
              │   Auth   │     │  Tasks   │
              │ Service  │     │ Service  │
              │  :5010   │     │  :5020   │
              └──────────┘     └──────────┘
```

| Service | Location | External Port | Role |
|---------|----------|---------------|------|
| Gateway | `gateway/` | 5000 | HTTP reverse proxy — routes requests to backend services |
| Auth | `services/auth/` | 5010 | User registration, login, JWT token issuance and verification |
| Tasks | `services/tasks/` | 5020 | Task CRUD REST API (API-only service) |
| Frontend | `services/frontend/` | 5030 | Server-rendered UI (BFF) that calls auth and task APIs |

### Routing

The gateway routes requests by URL prefix:

| Pattern | Destination |
|---------|-------------|
| `/api/auth/*` | Auth service |
| `/api/tasks/*` | Task service |
| `/*` (everything else) | Frontend service (web UI) |

### Authentication

Authentication uses **RS256 JWT tokens** with asymmetric keys across services:

1. User registers or logs in via the Auth service
2. Auth service returns a JWT (24h expiry) containing `user_id`, `username`, `iat`, `exp`
3. Client sends `Authorization: Bearer <token>` on subsequent requests
4. Auth service signs tokens with `JWT_PRIVATE_KEY`
5. Frontend and task services verify tokens with `JWT_PUBLIC_KEY`
6. All task queries are filtered by `user_id` from the token — full tenant isolation

## Prerequisites

- Python 3.13+
- Docker and Docker Compose
- GNU Make (recommended for the test workflow)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS
make install
python keys/generate.py
python -m playwright install chromium
```

## Running the Stack

Start all services:

```bash
docker compose up -d --build
```

To use non-default local key files without editing compose files, set
`JWT_PRIVATE_KEY_FILE` / `JWT_PUBLIC_KEY_FILE` (and test equivalents) in `.env`.

Verify everything is healthy:

```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/auth/health
curl http://localhost:5000/health
```

Stop and clean up:

```bash
docker compose down -v --remove-orphans
```

There is also a helper script:

```bash
./scripts/deploy-local.sh up       # start
./scripts/deploy-local.sh health   # check gateway + frontend + auth health
./scripts/deploy-local.sh ps       # show running containers
./scripts/deploy-local.sh logs     # tail logs
./scripts/deploy-local.sh down     # stop and remove volumes
```

## API Reference

### Auth endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/register` | No | Register a new user |
| `POST` | `/api/auth/login` | No | Log in and receive a JWT |
| `GET` | `/api/auth/verify` | Yes | Verify a bearer token |
| `GET` | `/api/auth/health` | No | Health check |

### Task endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/tasks` | Yes | List tasks (supports `?status=`, `?priority=`, `?sort=`, `?order=`) |
| `POST` | `/api/tasks` | Yes | Create a task |
| `GET` | `/api/tasks/{id}` | Yes | Get a single task |
| `PUT` | `/api/tasks/{id}` | Yes | Update a task |
| `DELETE` | `/api/tasks/{id}` | Yes | Delete a task |
| `PATCH` | `/api/tasks/{id}/status` | Yes | Update task status only |
| `GET` | `/api/health` | No | Health check |

### Quick walkthrough

```bash
# Register
curl -s -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "secret123"}'

# Login (save the token)
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Create a task
curl -s -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Write tests", "priority": "high"}'

# List tasks
curl -s http://localhost:5000/api/tasks \
  -H "Authorization: Bearer $TOKEN"
```

## Testing

### Fast path (recommended)

Use Make targets to run the right suite without remembering long commands:

```bash
make help
make test-all-local     # no docker
make test-cov           # combined local coverage + gate from pyproject
make test-smoke         # docker stack + smoke checks
make test-e2e           # docker stack + browser e2e
make test-perf          # docker stack + mixed/auth/crud perf scenarios
```

If you are using a venv, activate it first (`source .venv/bin/activate` on Linux/macOS).

### Focused targets

```bash
# Service-local
make test-auth
make test-tasks
make test-frontend
make test-gateway

# Cross-cutting / marker-based
make test-cross-service
make test-resilience

# Individual layers
make test-auth-unit
make test-tasks-integration
make test-frontend-contract
```

### Coverage

```bash
# Per-service coverage
make test-auth-cov
make test-tasks-cov
make test-frontend-cov
make test-gateway-cov

# Combined coverage + XML report + fail gate
make test-cov
```

Coverage HTML outputs:
- `htmlcov/auth/index.html`
- `htmlcov/tasks/index.html`
- `htmlcov/frontend/index.html`
- `htmlcov/gateway/index.html`
- `htmlcov/index.html` (combined)

### Direct pytest/locust commands (optional)

```bash
# Service-local
python -m pytest services/auth/tests -v
python -m pytest services/frontend/tests -v
python -m pytest services/tasks/tests -v
python -m pytest gateway/tests -v

# Cross-service
python -m pytest tests/cross_service -v

# Smoke (requires running stack or TEST_BASE_URL)
TEST_BASE_URL=http://localhost:5000 python -m pytest tests/smoke -v

# E2E (requires running stack or TEST_BASE_URL)
python -m pytest tests/e2e -v --browser chromium

# Performance (requires running stack)
python -m locust -f tests/performance/locustfile.py \
  --host http://localhost:5000 \
  --tags mixed \
  --headless \
  --only-summary \
  --reset-stats \
  --exit-code-on-error 0 \
  --users 10 \
  --spawn-rate 3 \
  --run-time 60s \
  --csv results/local_mixed \
  --html results/local_mixed.html

python tests/performance/check_thresholds.py \
  --stats results/local_mixed_stats.csv \
  --thresholds tests/performance/thresholds.yml
```

## Repository Layout

```
gateway/                          API gateway (Flask reverse proxy)
  gateway_app/
    routes.py                     Proxy routing logic
  config.py                       Gateway configuration
  Dockerfile
services/
  auth/                           Auth service
    auth_app/
      jwt.py                      JWT token creation
      models.py                   User model
      routes/api.py               Auth endpoints
    config.py
    Dockerfile
    tests/                        Unit, integration, contract tests
  frontend/                       Frontend BFF service
    frontend_app/
      auth.py                     JWT verification helper for session tokens
      models.py                   UI enums matching task API contract
      routes/views.py             HTML form routes (login, register, task pages)
      templates/                  Jinja2 templates
      static/                     CSS assets
    config.py
    Dockerfile
    tests/                        Integration tests for HTML/UI flow
  tasks/                          Task service
    task_app/
      auth.py                     JWT verification decorator
      models.py                   Task model + enums
      routes/
        api.py                    REST API endpoints
    config.py
    Dockerfile
    tests/                        Unit, integration, contract tests
shared/                           Test-only shared utilities
contracts/
  auth_openapi.yaml               Auth service OpenAPI spec
  tasks_openapi.yaml              Task service OpenAPI spec
  jwt_contract.yaml               JWT claims and algorithm contract
tests/
  cross_service/                  Auth + Task integration tests
  e2e/                            Playwright browser tests
    pages/                        Page object models
  performance/                    Locust scenarios + perf threshold checker
  smoke/                          Gateway smoke tests
docker-compose.yml                Production/development stack
docker-compose.test.yml           Test stack (isolated databases)
.env.example                      Environment variable template
.github/workflows/                CI/CD pipelines
```

## Contracts

API contracts live in `contracts/`:

- `auth_openapi.yaml` — Auth service OpenAPI spec
- `tasks_openapi.yaml` — Task service OpenAPI spec
- `jwt_contract.yaml` — Shared JWT claims and algorithm contract

Contract tests are in each service's `tests/contracts/` directory and in `tests/cross_service/test_jwt_contract.py`.

## CI/CD

Four GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `pr.yml` | Pull requests to main | Lint + per-service tests (with per-service coverage XML artifacts) + cross-service + smoke (only for changed services via path-based detection) |
| `main.yml` | Push to main | Build full stack, health checks, smoke tests, short mixed Locust perf gate |
| `release.yml` | Tag push | Build/push images, staging smoke gate, then parallel staging e2e + staging perf gate, then production smoke |
| `pr-nightly.yml` | Scheduled (nightly) | Full regression tests in one combined coverage run (HTML + XML artifact, fail gate from pyproject) + nightly Locust perf runs (mixed + auth + crud) |

PR checks use `dorny/paths-filter` so that changing files in `services/auth/` only triggers auth-tests and cross-service-tests, not the entire suite. The nightly run covers everything unconditionally as a safety net.

## Environment Variables

All configurable via environment or `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_PRIVATE_KEY_PATH` | `keys/dev.private.pem` | Auth-service private signing key path |
| `JWT_PUBLIC_KEY_PATH` | `keys/dev.public.pem` | JWT verification key path (frontend + task + auth verify endpoint) |
| `JWT_PRIVATE_KEY_FILE` | `./keys/dev.private.pem` | Host-side private key file for `docker-compose.yml` bind mount |
| `JWT_PUBLIC_KEY_FILE` | `./keys/dev.public.pem` | Host-side public key file for `docker-compose.yml` bind mount |
| `TEST_JWT_PRIVATE_KEY_FILE` | `./keys/dev.private.pem` | Host-side private key file for `docker-compose.test.yml` bind mount |
| `TEST_JWT_PUBLIC_KEY_FILE` | `./keys/dev.public.pem` | Host-side public key file for `docker-compose.test.yml` bind mount |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime in hours |
| `JWT_CLOCK_SKEW_SECONDS` | `30` | Allowed clock drift for token verification |
| `AUTH_SERVICE_URL` | `http://auth-service:5000` | Auth service base URL (used by frontend and gateway) |
| `AUTH_SERVICE_TIMEOUT` | `5` | Timeout in seconds for frontend auth service calls |
| `TASK_SERVICE_URL` | `http://task-service:5000` | Task service base URL (used by frontend and gateway) |
| `TASK_SERVICE_TIMEOUT` | `5` | Timeout in seconds for frontend task service calls |
| `FRONTEND_SERVICE_URL` | `http://frontend-service:5000` | Frontend service base URL (used by gateway catch-all routes) |
| `PROXY_TIMEOUT` | `10` | Gateway proxy timeout in seconds |
| `DATABASE_URL` | `sqlite:///instance/<service>.db` | SQLAlchemy database URI |
| `TEST_BASE_URL` | `http://localhost:5000` | Base URL for smoke and E2E tests |
| `E2E_COMPOSE_FILE` | `docker-compose.test.yml` | Compose file used by E2E test fixtures |

## Baseline Tag

The original monolith codebase is preserved as Git tag `v1-monolith` for before/after comparison.
