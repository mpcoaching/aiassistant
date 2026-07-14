#!/usr/bin/env bash
# Deploy Live — deploys the SAME immutable <git-sha> as dev. Rollback = redeploy
# a prior tag. NEVER rebuilds on promotion.
#   IMAGE_TAG  : the immutable <git-sha> (required)
#   REGISTRY_URL : registry.local.test/aiassistant (default)
set -euo pipefail

export IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG (git sha) is required}"
export REGISTRY_URL="${REGISTRY_URL:-registry.local.test/aiassistant}"
COMPOSE_FILE="environments/live/compose.yml"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$HERE"

echo "[deploy-live] tag=$IMAGE_TAG registry=$REGISTRY_URL"

# Phase 7.5 gate: require a green backup-validation marker before first live.
if [[ ! -f "cicd/state/backup-validation-green" ]]; then
  echo "[deploy-live] BLOCKED: Phase 7.5 backup/restore validation not marked green."
  echo "  Create cicd/state/backup-validation-green after a successful restore test."
  exit 1
fi

bash cicd/scripts/validate-promotion.sh "$COMPOSE_FILE"

echo "[deploy-live] pulling images..."
docker compose -f "$COMPOSE_FILE" pull

echo "[deploy-live] reconciling live environment..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[deploy-live] done. Verify: curl -fsS https://agent.live.local.test"
