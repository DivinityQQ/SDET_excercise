# SDET Exercise

A task management application built to demonstrate Software Development Engineer in Test (SDET) skills, including API testing, UI testing, mocking, and CI/CD pipelines.

## What's in this repo

- **Flask web app** - Simple task manager with CRUD operations
- **REST API** - JSON endpoints for task management
- **Test suites** - Unit, integration, E2E, smoke, and mock tests
- **Docker runtime** - Gunicorn-based container build
- **CI/CD pipelines** - PR checks, dev deploy, and release workflow

## Project structure

```
app/
├── models.py           # SQLAlchemy Task model
├── routes/
│   ├── api.py          # REST API endpoints
│   └── views.py        # Web UI routes
├── templates/          # Jinja2 HTML templates
└── static/             # CSS styles

tests/
├── unit/               # Fast unit tests
├── integration/        # API integration tests
├── e2e/                # Playwright browser tests
│   └── pages/          # Page Object Model classes
├── smoke/              # Post-deploy health checks
└── mocks/              # Mock/unit tests

Dockerfile              # Container build (gunicorn)
docker-compose.yml      # Dev/Staging/Prod local envs
wsgi.py                 # Gunicorn entrypoint
scripts/
└── deploy-local.sh      # Local deploy helper
```

## Setup

### Requirements

- Python 3.13+
- pip

### Installation

```bash
# Clone the repo
git clone https://github.com/DivinityQQ/SDET_excercise.git
cd SDET_excercise

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for UI tests)
playwright install chromium
```

## Running the app (local)

```bash
flask run
```

Visit http://127.0.0.1:5000

## Docker environments (DEV/STAGING/PROD)

```bash
# Start all three environments
docker compose up -d

# Or start a single environment
docker compose up -d dev

# Helper script
./scripts/deploy-local.sh dev
```

Health checks:

```bash
curl http://localhost:5001/api/health  # DEV
curl http://localhost:5002/api/health  # STAGING
curl http://localhost:5003/api/health  # PROD
```

## Running tests

### All tests
```bash
pytest
```

### By test type
```bash
# Unit tests
pytest tests/unit tests/mocks -v

# Integration (API) tests
pytest tests/integration -v

# E2E (Playwright) tests
pytest tests/e2e -v

# UI smoke only (fast PR signal)
pytest tests/e2e -m "smoke" -v

# Smoke tests (post-deploy)
pytest tests/smoke -v
```

### With coverage
```bash
pytest tests/ --cov=app --cov-report=html:reports/coverage
```

### Linting
```bash
ruff check .
ruff check . --fix  # auto-fix issues
```

## CI/CD

GitHub Actions simulates a multi-stage pipeline:

- PR flow smoke change (safe to remove after verification).

- **PR Checks** (`.github/workflows/pr.yml`)
  - Lint, unit tests, integration tests
  - UI smoke tests only (fast signal)
- **Dev Deployment** (`.github/workflows/main.yml`)
  - Build/push dev image
  - Run container on `:5001` and execute smoke tests
- **Release Pipeline** (`.github/workflows/release.yml`)
  - Tag `v*` builds/pushes image
  - Deploy STAGING + E2E tests
  - Manual approval gate for PROD
  - Smoke tests against PROD

### GitHub settings to enable approvals

1. **Settings → Environments**: create `staging` and `production`
2. **production**: enable *Required reviewers* for approval gate
3. **Settings → Actions → General**: enable **Read and write permissions** for `GITHUB_TOKEN`

### Local pipeline walkthrough

```bash
# Start all environments
docker compose up -d

# Check health
curl http://localhost:5001/api/health
curl http://localhost:5002/api/health
curl http://localhost:5003/api/health

# Tag a release to trigger release pipeline
git tag v1.0.0
git push origin v1.0.0
```

## VSCode setup

1. Install the **Python** extension
2. Install the **Ruff** extension for linting
3. Open the Testing panel to discover and run tests
