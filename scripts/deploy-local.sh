#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-up}
PROJECT_NAME=${PROJECT_NAME:-taskapp}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}

compose() {
  docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" "$@"
}

case "${ACTION}" in
  up)
    compose up -d --build
    ;;
  down)
    compose down -v --remove-orphans
    ;;
  ps)
    compose ps
    ;;
  logs)
    compose logs -f
    ;;
  health)
    echo "Gateway health"
    curl -fsS "http://localhost:5000/api/health" | (command -v jq >/dev/null 2>&1 && jq . || cat)
    echo
    echo "Frontend health via gateway"
    curl -fsS "http://localhost:5000/health" | (command -v jq >/dev/null 2>&1 && jq . || cat)
    echo
    echo "Auth health via gateway"
    curl -fsS "http://localhost:5000/api/auth/health" | (command -v jq >/dev/null 2>&1 && jq . || cat)
    echo
    ;;
  *)
    echo "Usage: $0 [up|down|ps|logs|health]"
    exit 1
    ;;
esac
