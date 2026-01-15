# SDET Exercise

A task management application built to demonstrate Software Development Engineer in Test (SDET) skills, including API testing, UI testing, mocking, and CI/CD pipelines.

## What's in this repo

- **Flask web app** - Simple task manager with CRUD operations
- **REST API** - JSON endpoints for task management
- **API tests** - Pytest tests for endpoint validation
- **UI tests** - Playwright browser automation tests
- **Mock tests** - Unit tests demonstrating mocking patterns
- **CI/CD pipeline** - GitHub Actions workflow

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
├── api/                # API integration tests
│   ├── test_tasks_crud.py
│   └── test_validation.py
├── ui/                 # Playwright browser tests
│   ├── pages/          # Page Object Model classes
│   └── test_task_flows.py
└── mocks/              # Mock/unit tests
    └── test_external_service.py
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

## Running the app

```bash
flask run
```

Visit http://127.0.0.1:5000

## Running tests

### All tests
```bash
pytest
```

### By test type
```bash
# API tests
pytest tests/api -m "api"

# UI tests
pytest tests/ui -m "ui"

# Mock tests
pytest tests/mocks

# Smoke tests (quick validation)
pytest -m "smoke"
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

GitHub Actions runs automatically on push to `main` and on pull requests:

1. **Lint** - Code quality check with ruff
2. **API tests** - Backend endpoint tests
3. **UI tests** - Playwright browser tests
4. **Mock tests** - Unit tests with mocking

See `.github/workflows/tests.yml` for configuration.

## VSCode setup

1. Install the **Python** extension
2. Install the **Ruff** extension for linting
3. Open the Testing panel to discover and run tests
