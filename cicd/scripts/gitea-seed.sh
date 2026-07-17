#!/usr/bin/env bash
# One-time bootstrap for the Gitea source-of-truth used by TeamCity.
# Run AFTER: docker compose -f infrastructure/compose.yml up -d && docker compose -f platform/compose.yml up -d
#
# Creates the `aiassistant` repo under the `ai` CI admin account, installs a
# read/write deploy key, and registers a webhook to the TeamCity server.
# Requires Gitea to be healthy.
set -euo pipefail

GITEA_URL="${GITEA_URL:-https://gitea.local.test}"
ADMIN_USER="${GITEA_ADMIN_USER:-ai}"
ADMIN_PASS="${GITEA_ADMIN_PASS:-changeme}"
ORG="${GITEA_ORG:-ai}"
REPO="${GITEA_REPO:-aiassistant}"
TEAMCITY_URL="${TEAMCITY_URL:-http://teamcity-server:8111}"
DEPLOY_KEY_PATH="${DEPLOY_KEY_PATH:-$HOME/.ssh/gitea_deploy.pub}"

# Gitea is reached via nginx (https://gitea.local.test:443) which terminates the
# self-signed local.test cert. The WSL host cannot reach Gitea's internal :3000
# (Docker Desktop network isolation), so we always go through nginx with -k.
CURL="curl -fsS -k"
# Bootstrap API calls authenticate as the admin user directly (basic auth).
# No long-lived token is needed — the webhook simply POSTs to teamcity-server,
# which Gitea reaches over the internal docker network.
AUTH=(-u "$ADMIN_USER:$ADMIN_PASS")

echo "Waiting for Gitea at $GITEA_URL ..."
until $CURL "$GITEA_URL/api/v1/version" >/dev/null 2>&1; do sleep 3; done

# Repo. NOTE: the `ai` account is a *user* (the CI admin created for seeding),
# not an org — Gitea forbids an org name equal to an existing username, so the
# repo is created under the authenticated user `ai`. The resulting URL
# (https://gitea.local.test/ai/aiassistant.git) is identical either way.
$CURL -X POST "$GITEA_URL/api/v1/user/repos" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$REPO\",\"private\":false,\"auto_init\":true}" || true

# Deploy key (read/write)
if [ -f "$DEPLOY_KEY_PATH" ]; then
  KEY=$(cat "$DEPLOY_KEY_PATH")
  $CURL -X POST "$GITEA_URL/api/v1/repos/$ORG/$REPO/keys" "${AUTH[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"teamcity-deploy\",\"key\":\"$KEY\",\"read_only\":false}" || true
fi

# Webhook -> TeamCity (VCS trigger). Idempotent: skip if a hook with the same
# target URL already exists (avoids duplicate VCS triggers on re-runs).
HOOK_URL="$TEAMCITY_URL/app/rest/vcs-root-instances/commitHookNotification?locator=vcsRoot:(type:git)"
if ! curl -fsS -k "${AUTH[@]}" "$GITEA_URL/api/v1/repos/$ORG/$REPO/hooks" \
     | grep -q "$HOOK_URL"; then
  $CURL -X POST "$GITEA_URL/api/v1/repos/$ORG/$REPO/hooks" "${AUTH[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"type\":\"gitea\",\"active\":true,\"events\":[\"push\",\"pull_request\"],\
        \"config\":{\"url\":\"$HOOK_URL\",\"content_type\":\"json\"}}" || true
else
  echo "Webhook already present, skipping."
fi

echo "Gitea bootstrap complete: $GITEA_URL/$ORG/$REPO"
