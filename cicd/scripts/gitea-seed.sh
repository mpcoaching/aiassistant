#!/usr/bin/env bash
# One-time bootstrap for the Gitea source-of-truth used by TeamCity.
# Run AFTER: docker compose -f infrastructure/compose.yml up -d && docker compose -f platform/compose.yml up -d
#
# Creates the `ai` org + `aiassistant` repo, installs a read/write deploy key,
# and registers a webhook to the TeamCity server. Requires Gitea to be healthy.
set -euo pipefail

GITEA_URL="${GITEA_URL:-http://gitea.local.test}"
ADMIN_USER="${GITEA_ADMIN_USER:-ai}"
ADMIN_PASS="${GITEA_ADMIN_PASS:-changeme}"
ORG="${GITEA_ORG:-ai}"
REPO="${GITEA_REPO:-aiassistant}"
TEAMCITY_URL="${TEAMCITY_URL:-http://teamcity-server:8111}"
DEPLOY_KEY_PATH="${DEPLOY_KEY_PATH:-$HOME/.ssh/gitea_deploy.pub}"

echo "Waiting for Gitea at $GITEA_URL ..."
until curl -fsS "$GITEA_URL/api/v1/version" >/dev/null 2>&1; do sleep 3; done

# Admin token (idempotent-ish: create, ignore if exists)
TOKEN_NAME="teamcity-bot"
TOKEN=$(curl -fsS -X POST "$GITEA_URL/api/v1/users/$ADMIN_USER/tokens" \
  -H "Content-Type: application/json" \
  -u "$ADMIN_USER:$ADMIN_PASS" \
  -d "{\"name\":\"$TOKEN_NAME\"}" | sed -E 's/.*"sha1":"([^"]+)".*/\1/')
AUTH="-H Authorization: token $TOKEN"

# Org + repo
curl -fsS -X PUT "$GITEA_URL/api/v1/orgs/$ORG" $AUTH \
  -H "Content-Type: application/json" -d "{\"username\":\"$ORG\"}" || true
curl -fsS -X POST "$GITEA_URL/api/v1/org/$ORG/repos" $AUTH \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$REPO\",\"private\":false,\"auto_init\":true}" || true

# Deploy key (read/write)
if [ -f "$DEPLOY_KEY_PATH" ]; then
  KEY=$(cat "$DEPLOY_KEY_PATH")
  curl -fsS -X POST "$GITEA_URL/api/v1/repos/$ORG/$REPO/keys" $AUTH \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"teamcity-deploy\",\"key\":\"$KEY\",\"read_only\":false}" || true
fi

# Webhook -> TeamCity (VCS trigger)
curl -fsS -X POST "$GITEA_URL/api/v1/repos/$ORG/$REPO/hooks" $AUTH \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"gitea\",\"active\":true,\"events\":[\"push\",\"pull_request\"],\
      \"config\":{\"url\":\"$TEAMCITY_URL/app/rest/vcs-root-instances/commitHookNotification?locator=vcsRoot:(type:git)\",\
      \"content_type\":\"json\"}}" || true

echo "Gitea bootstrap complete: $GITEA_URL/$ORG/$REPO"
