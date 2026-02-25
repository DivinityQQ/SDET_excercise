#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:5000}"
MAX_ATTEMPTS="${2:-45}"
SLEEP_SECONDS="${3:-2}"

BASE_URL="${BASE_URL%/}"
GATEWAY_HEALTH_URL="${BASE_URL}/api/health"
AUTH_HEALTH_URL="${BASE_URL}/api/auth/health"

for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
  if curl -sf "${GATEWAY_HEALTH_URL}" > /dev/null && curl -sf "${AUTH_HEALTH_URL}" > /dev/null; then
    exit 0
  fi
  sleep "${SLEEP_SECONDS}"
done

echo "Health checks failed after ${MAX_ATTEMPTS} attempts." >&2
echo "Checked: ${GATEWAY_HEALTH_URL} and ${AUTH_HEALTH_URL}" >&2

if (( $# > 3 )); then
  shift 3
  "$@" || true
fi

exit 1
