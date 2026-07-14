#!/usr/bin/env bash
# Rollback — redeploy a prior immutable <git-sha> tag to the target environment.
# Usage: rollback.sh <prior-tag> [env]
#   env defaults to "live". Images are already present in the registry (immutable).
set -euo pipefail

PRIOR_TAG="${1:?usage: rollback.sh <prior-tag> [env]}"
ENV="${2:-live}"
export REGISTRY_URL="${REGISTRY_URL:-registry.local.test/aiassistant}"
export IMAGE_TAG="$PRIOR_TAG"
COMPOSE_FILE="environments/${ENV}/compose.yml"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$HERE"

echo "[rollback] env=$ENV tag=$PRIOR_TAG"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[rollback] [FAIL] compose file not found: $COMPOSE_FILE"; exit 1
fi

bash cicd/scripts/validate-promotion.sh "$COMPOSE_FILE"

echo "[rollback] pulling prior tag..."
docker compose -f "$COMPOSE_FILE" pull

echo "[rollback] reconciling $ENV environment to $PRIOR_TAG..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[rollback] done. $ENV is now on $PRIOR_TAG."
