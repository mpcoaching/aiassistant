#!/usr/bin/env bash
# Deploy Development — pulls immutable images from the private registry and
# reconciles the dev environment. NEVER rebuilds on promotion.
#   IMAGE_TAG  : the immutable <git-sha> (required)
#   REGISTRY_URL : registry.local.test/aiassistant (default)
set -euo pipefail

export IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG (git sha) is required}"
export REGISTRY_URL="${REGISTRY_URL:-registry.local.test/aiassistant}"
COMPOSE_FILE="environments/dev/compose.yml"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$HERE"

echo "[deploy-dev] tag=$IMAGE_TAG registry=$REGISTRY_URL"

bash cicd/scripts/validate-promotion.sh "$COMPOSE_FILE"

echo "[deploy-dev] pulling images..."
# Pull from the private registry when reachable (TeamCity flow). When the host
# docker daemon cannot trust registry.local.test (e.g. WSL2/Docker Desktop
# without the CA installed or an insecure-registry entry), skip the pull and
# rely on images already present in the local daemon (e.g. built locally).
if [[ "${COMPOSE_PULL:-true}" == "true" ]]; then
  if docker compose -f "$COMPOSE_FILE" pull; then
    echo "[deploy-dev] pull OK"
  else
    echo "[deploy-dev] WARN: pull failed (registry unreachable / untrusted); using local images if present."
  fi
else
  echo "[deploy-dev] COMPOSE_PULL=false — skipping registry pull, using local images."
fi

echo "[deploy-dev] reconciling dev environment..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[deploy-dev] done. Verify: curl -fsS https://agent.dev.local.test"
