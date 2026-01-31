#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/deploy-local.sh [dev|staging|prod] [version]

ENVIRONMENT=${1:-dev}
VERSION=${2:-latest}

echo "Deploying version ${VERSION} to ${ENVIRONMENT}..."

docker compose build
docker compose up -d "${ENVIRONMENT}"

echo "Waiting for ${ENVIRONMENT} to be ready..."
sleep 3

PORT=5001
if [[ "${ENVIRONMENT}" == "staging" ]]; then
  PORT=5002
elif [[ "${ENVIRONMENT}" == "prod" ]]; then
  PORT=5003
fi

echo "Health check:"
if command -v jq >/dev/null 2>&1; then
  curl -s "http://localhost:${PORT}/api/health" | jq .
else
  curl -s "http://localhost:${PORT}/api/health"
  echo
fi

echo "Deployment to ${ENVIRONMENT} complete!"
