#!/bin/bash
set -euo pipefail

RUNNER_CONTAINER="infra_gitea_runner"
MAX_AGE_MINUTES=30

if ! docker ps --filter "name=${RUNNER_CONTAINER}" --filter "status=running" --format "{{.Names}}" | grep -q "${RUNNER_CONTAINER}"; then
  echo "Runner container not running, starting..."
  docker compose -f infrastructure/compose.yml up -d "${RUNNER_CONTAINER}"
  exit 0
fi

LAST_LOG_TIME=$(docker logs "${RUNNER_CONTAINER}" --since "${MAX_AGE_MINUTES}m" --format "{{.Time}}" 2>/dev/null | tail -1 || true)

if [ -z "${LAST_LOG_TIME}" ]; then
  echo "No recent logs from runner, restarting..."
  docker compose -f infrastructure/compose.yml restart "${RUNNER_CONTAINER}"
fi
