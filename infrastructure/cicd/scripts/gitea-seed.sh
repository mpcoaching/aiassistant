#!/usr/bin/env bash
# One-time bootstrap for the Gitea source-of-truth.
# Run AFTER: docker compose -f infrastructure/compose.yml up -d && docker compose -f platform/compose.yml up -d
#
# Creates the `aiassistant` repo under the `ai` CI admin account and installs a
# read/write deploy key.
# Requires Gitea to be healthy.
set -euo pipefail

GITEA_URL="${GITEA_URL:-https://gitea.local.test}"
ADMIN_USER="${GITEA_ADMIN_USER:-ai}"
ADMIN_PASS="${GITEA_ADMIN_PASS:-changeme}"
ORG="${GITEA_ORG:-ai}"
REPO="${GITEA_REPO:-aiassistant}"
DEPLOY_KEY_PATH="${DEPLOY_KEY_PATH:-$HOME/.ssh/gitea_deploy.pub}"

CURL="curl -fsS -k"
AUTH=(-u "$ADMIN_USER:$ADMIN_PASS")

echo "Waiting for Gitea at $GITEA_URL ..."
until $CURL "$GITEA_URL/api/v1/version" >/dev/null 2>&1; do sleep 3; done

$CURL -X POST "$GITEA_URL/api/v1/user/repos" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$REPO\",\"private\":false,\"auto_init\":true}" || true

if [ -f "$DEPLOY_KEY_PATH" ]; then
  KEY=$(cat "$DEPLOY_KEY_PATH")
  $CURL -X POST "$GITEA_URL/api/v1/repos/$ORG/$REPO/keys" "${AUTH[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"gitea-actions-deploy\",\"key\":\"$KEY\",\"read_only\":false}" || true
fi

echo "Gitea bootstrap complete: $GITEA_URL/$ORG/$REPO"
