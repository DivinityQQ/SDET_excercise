# SDET Exercise - Microservices Edition

A task management application used to practice SDET workflows in a microservices architecture.

## Architecture

- Gateway: `http://localhost:5000`
- Auth service: `http://localhost:5010` (internal container port `5000`)
- Task service: `http://localhost:5020` (internal container port `5000`)

Request flow:

```text
Client -> Gateway (/api/auth/*, /api/tasks/*, /)
       -> Auth Service (JWT issue/verify)
       -> Task Service (task CRUD + web UI)
```

## Repository Layout

```text
gateway/
services/
  auth/
  tasks/
shared/               # test-only helpers
contracts/
  auth_openapi.yaml
  tasks_openapi.yaml
  jwt_contract.yaml
tests/
  cross_service/
  e2e/
  smoke/
  mocks/
```

## Setup

```bash
python -m venv venv
venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
playwright install chromium
```

## Run Locally with Docker Compose

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:5000/api/health
curl http://localhost:5000/api/auth/health
```

Stop and clean volumes:

```bash
docker compose down -v --remove-orphans
```

You can also use:

```bash
./scripts/deploy-local.sh up
./scripts/deploy-local.sh health
./scripts/deploy-local.sh down
```

## Test Commands

Per-service suites:

```bash
cd services/auth && PYTHONPATH=../.. pytest tests -v
cd services/tasks && PYTHONPATH=../.. pytest tests -v
cd gateway && PYTHONPATH=.. pytest tests -v
```

Cross-service and shared suites (repo root):

```bash
PYTHONPATH=. pytest tests/cross_service -v
PYTHONPATH=. pytest tests/mocks -v
```

Smoke tests (requires running stack):

```bash
TEST_BASE_URL=http://localhost:5000 pytest tests/smoke -v
```

E2E tests:

- If `TEST_BASE_URL` is set, tests run against that stack.
- If not set, tests try to start `docker-compose.test.yml` automatically.

```bash
pytest tests/e2e -v --browser chromium
```

## Contracts

- `contracts/auth_openapi.yaml`: Auth service contract
- `contracts/tasks_openapi.yaml`: Task service contract
- `contracts/jwt_contract.yaml`: shared JWT claims/algorithm contract

Contract tests live under each service plus `tests/cross_service/test_jwt_contract.py`.

## Baseline Tag

The monolith baseline is preserved as Git tag `v1-monolith` for before/after comparison.
