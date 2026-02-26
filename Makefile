.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTEST ?= $(PYTHON) -m pytest
BASE_URL ?= http://localhost:5000

SMOKE_E2E_COMPOSE_PROJECT ?= taskapp-local
SMOKE_E2E_COMPOSE_FILE ?= docker-compose.test.yml

PERF_COMPOSE_PROJECT ?= taskapp-local-perf
PERF_COMPOSE_FILE ?= docker-compose.yml
PERF_RUNTIME ?= 60s

.PHONY: help \
	lint \
	test-auth-unit test-auth-integration test-auth-contract test-auth \
	test-tasks-unit test-tasks-integration test-tasks-contract test-tasks \
	test-frontend-integration test-frontend-contract test-frontend \
	test-gateway-unit test-gateway-integration test-gateway \
	test-cross-service test-unit test-integration test-contract test-resilience \
	stack-up stack-down perf-stack-up perf-stack-down \
	test-smoke test-e2e \
	test-perf-mixed test-perf-auth test-perf-crud test-perf \
	test-all-local test-all

help: ## Show grouped Make targets.
	@echo "Service tests (no docker):"
	@echo "  make test-auth-unit"
	@echo "  make test-auth-integration"
	@echo "  make test-auth-contract"
	@echo "  make test-auth"
	@echo "  make test-tasks-unit"
	@echo "  make test-tasks-integration"
	@echo "  make test-tasks-contract"
	@echo "  make test-tasks"
	@echo "  make test-frontend-integration"
	@echo "  make test-frontend-contract"
	@echo "  make test-frontend"
	@echo "  make test-gateway-unit"
	@echo "  make test-gateway-integration"
	@echo "  make test-gateway"
	@echo ""
	@echo "Cross-cutting tests (no docker):"
	@echo "  make test-cross-service"
	@echo "  make test-unit"
	@echo "  make test-integration"
	@echo "  make test-contract"
	@echo "  make test-resilience"
	@echo ""
	@echo "Stack tests (docker):"
	@echo "  make test-smoke"
	@echo "  make test-e2e"
	@echo ""
	@echo "Performance tests (docker + locust):"
	@echo "  make test-perf-mixed"
	@echo "  make test-perf-auth"
	@echo "  make test-perf-crud"
	@echo "  make test-perf"
	@echo ""
	@echo "Aggregate:"
	@echo "  make test-all-local"
	@echo "  make test-all"
	@echo ""
	@echo "Utility:"
	@echo "  make lint"
	@echo "  make stack-up"
	@echo "  make stack-down"

lint: ## Run lint checks.
	$(PYTHON) -m ruff check .

# ---- Service tests ----------------------------------------------------------

test-auth-unit: ## Run auth unit tests.
	$(PYTEST) services/auth/tests/unit -v

test-auth-integration: ## Run auth integration tests.
	$(PYTEST) services/auth/tests/integration -v

test-auth-contract: ## Run auth contract tests.
	$(PYTEST) services/auth/tests/contracts -v

test-auth: ## Run all auth tests.
	$(PYTEST) services/auth/tests -v

test-tasks-unit: ## Run tasks unit tests.
	$(PYTEST) services/tasks/tests/unit -v

test-tasks-integration: ## Run tasks integration tests.
	$(PYTEST) services/tasks/tests/integration -v

test-tasks-contract: ## Run tasks contract tests.
	$(PYTEST) services/tasks/tests/contracts -v

test-tasks: ## Run all tasks tests.
	$(PYTEST) services/tasks/tests -v

test-frontend-integration: ## Run frontend integration tests.
	$(PYTEST) services/frontend/tests/integration -v

test-frontend-contract: ## Run frontend contract tests.
	$(PYTEST) services/frontend/tests/contracts -v

test-frontend: ## Run all frontend tests.
	$(PYTEST) services/frontend/tests -v

test-gateway-unit: ## Run gateway unit tests.
	$(PYTEST) gateway/tests/unit -v

test-gateway-integration: ## Run gateway integration tests.
	$(PYTEST) gateway/tests/integration -v

test-gateway: ## Run all gateway tests.
	$(PYTEST) gateway/tests -v

# ---- Cross-cutting tests ----------------------------------------------------

test-cross-service: ## Run cross-service tests (requires auth+tasks dependencies).
	$(PYTEST) tests/cross_service -v

test-unit: ## Run all unit tests across services and gateway.
	$(PYTEST) services/auth/tests services/tasks/tests services/frontend/tests gateway/tests -m unit -v

test-integration: ## Run all integration tests across services and gateway.
	$(PYTEST) services/auth/tests services/tasks/tests services/frontend/tests gateway/tests -m integration -v

test-contract: ## Run all contract tests across services.
	$(PYTEST) services/auth/tests/contracts services/tasks/tests/contracts services/frontend/tests/contracts -v

test-resilience: ## Run all resilience-marked tests.
	$(PYTEST) services/tasks/tests gateway/tests tests/cross_service -m resilience -v

# ---- Stack lifecycle (smoke/e2e) -------------------------------------------

stack-up: ## Start local test stack and wait for health.
	docker compose -p "$(SMOKE_E2E_COMPOSE_PROJECT)" -f "$(SMOKE_E2E_COMPOSE_FILE)" up -d --build
	scripts/wait-for-health.sh "$(BASE_URL)" 45 2 docker compose -p "$(SMOKE_E2E_COMPOSE_PROJECT)" -f "$(SMOKE_E2E_COMPOSE_FILE)" logs

stack-down: ## Tear down local test stack.
	docker compose -p "$(SMOKE_E2E_COMPOSE_PROJECT)" -f "$(SMOKE_E2E_COMPOSE_FILE)" down -v --remove-orphans

test-smoke: ## Run smoke tests with managed stack lifecycle.
	trap '$(MAKE) --no-print-directory stack-down' EXIT; \
	$(MAKE) --no-print-directory stack-up; \
	TEST_BASE_URL="$(BASE_URL)" $(PYTEST) tests/smoke -v

test-e2e: ## Run browser E2E tests with managed stack lifecycle.
	trap '$(MAKE) --no-print-directory stack-down' EXIT; \
	$(MAKE) --no-print-directory stack-up; \
	$(PYTHON) -m playwright install chromium; \
	TEST_BASE_URL="$(BASE_URL)" $(PYTEST) tests/e2e -v --browser chromium

# ---- Stack lifecycle (performance) -----------------------------------------

perf-stack-up: ## Start performance stack and wait for health.
	docker compose -p "$(PERF_COMPOSE_PROJECT)" -f "$(PERF_COMPOSE_FILE)" up -d --build
	scripts/wait-for-health.sh "$(BASE_URL)" 45 2 docker compose -p "$(PERF_COMPOSE_PROJECT)" -f "$(PERF_COMPOSE_FILE)" logs

perf-stack-down: ## Tear down performance stack.
	docker compose -p "$(PERF_COMPOSE_PROJECT)" -f "$(PERF_COMPOSE_FILE)" down -v --remove-orphans

test-perf-mixed: ## Run mixed performance scenario with managed stack lifecycle.
	trap '$(MAKE) --no-print-directory perf-stack-down' EXIT; \
	$(MAKE) --no-print-directory perf-stack-up; \
	mkdir -p results; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags mixed --users 10 --spawn-rate 3 --run-time "$(PERF_RUNTIME)" --csv results/local_mixed --html results/local_mixed.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_mixed_stats.csv --thresholds tests/performance/thresholds.yml

test-perf-auth: ## Run auth-storm performance scenario with managed stack lifecycle.
	trap '$(MAKE) --no-print-directory perf-stack-down' EXIT; \
	$(MAKE) --no-print-directory perf-stack-up; \
	mkdir -p results; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags auth --users 10 --spawn-rate 5 --run-time "$(PERF_RUNTIME)" --csv results/local_auth --html results/local_auth.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_auth_stats.csv --thresholds tests/performance/thresholds.yml

test-perf-crud: ## Run CRUD performance scenario with managed stack lifecycle.
	trap '$(MAKE) --no-print-directory perf-stack-down' EXIT; \
	$(MAKE) --no-print-directory perf-stack-up; \
	mkdir -p results; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags crud --users 10 --spawn-rate 3 --run-time "$(PERF_RUNTIME)" --csv results/local_crud --html results/local_crud.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_crud_stats.csv --thresholds tests/performance/thresholds.yml

test-perf: ## Run mixed, auth, and CRUD performance scenarios in one stack session.
	trap '$(MAKE) --no-print-directory perf-stack-down' EXIT; \
	$(MAKE) --no-print-directory perf-stack-up; \
	mkdir -p results; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags mixed --users 10 --spawn-rate 3 --run-time "$(PERF_RUNTIME)" --csv results/local_mixed --html results/local_mixed.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_mixed_stats.csv --thresholds tests/performance/thresholds.yml; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags auth --users 10 --spawn-rate 5 --run-time "$(PERF_RUNTIME)" --csv results/local_auth --html results/local_auth.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_auth_stats.csv --thresholds tests/performance/thresholds.yml; \
	$(PYTHON) -m locust -f tests/performance/locustfile.py --host "$(BASE_URL)" --headless --only-summary --reset-stats --exit-code-on-error 0 --tags crud --users 10 --spawn-rate 3 --run-time "$(PERF_RUNTIME)" --csv results/local_crud --html results/local_crud.html; \
	$(PYTHON) tests/performance/check_thresholds.py --stats results/local_crud_stats.csv --thresholds tests/performance/thresholds.yml

# ---- Aggregate targets ------------------------------------------------------

test-all-local: ## Run all tests that do not require docker.
	$(MAKE) --no-print-directory lint
	$(MAKE) --no-print-directory test-auth
	$(MAKE) --no-print-directory test-tasks
	$(MAKE) --no-print-directory test-frontend
	$(MAKE) --no-print-directory test-gateway
	$(MAKE) --no-print-directory test-cross-service

test-all: ## Run all local, smoke, e2e, and performance checks.
	$(MAKE) --no-print-directory test-all-local
	$(MAKE) --no-print-directory test-smoke
	$(MAKE) --no-print-directory test-e2e
	$(MAKE) --no-print-directory test-perf
