#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Host-side deployment of the n8n service.
#
#   Usage: deploy-platform.sh <commit-sha>
#
# INVOKED BY: the CI `deploy-platform` step, AFTER the calling (bootstrap)
# command has already, on the host:
#   1. cd'd to $DEPLOY_DIR
#   2. verified the working tree is clean (never `git reset --hard`)
#   3. fetched Gitea state and verified the EXACT commit SHA exists
#   4. checked out EXACTLY that SHA (detached HEAD)
#
# Because bootstrap is performed by the caller BEFORE this script runs, a host
# on ANY prior commit can deploy a NEWER commit that introduces this script:
# this script itself is never required to pre-exist on the host.
#
# This script therefore ONLY:
#   - re-verifies HEAD == requested SHA (defensive double-check)
#   - converges ONLY the `n8n` service via docker compose
#
# It intentionally contains NO git checkout / fetch / clean-check / flock
# logic (those live in the CI caller) so that:
#   - it does not deadlock with the caller's flock (the caller holds the lock
#     across checkout + this deploy), and
#   - it never re-declares a checkout that the caller already performed.
#
# Does NOT: pull/build images, run the whole platform, `compose down`/`-v`, or
# touch .env (read only via --env-file .env). Sibling platform services and
# named volumes are left untouched.
# ----------------------------------------------------------------------------
set -euo pipefail

COMMIT_SHA="${1:-}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/agent99/projects/aiassistant}"

if [ -z "$COMMIT_SHA" ]; then
  echo "ERROR: missing commit SHA argument." >&2
  echo "       Usage: $0 <commit-sha>" >&2
  exit 1
fi

cd "$DEPLOY_DIR"

# Defensive: confirm we are exactly on the requested commit before converging.
HEAD_SHA="$(git rev-parse HEAD)"
if [ "$HEAD_SHA" != "$COMMIT_SHA" ]; then
  echo "ERROR: HEAD ($HEAD_SHA) != requested SHA ($COMMIT_SHA). Aborting deploy." >&2
  exit 1
fi

# --- Converge ONLY n8n -------------------------------------------------------
# --force-recreate ensures the n8n container is recreated and re-reads its
# bind mount (./custom-nodes:/home/node/.n8n/custom) so a custom-node change is
# loaded at startup (n8n reads N8N_CUSTOM_EXTENSIONS only at startup). No
# --pull / --build is used, so the n8n image tag on the host is unchanged.
docker compose \
  -f platform/compose.yml \
  --env-file .env \
  up -d --force-recreate n8n

echo ">> n8n converged at ${HEAD_SHA}"
echo ">> Platform deploy complete."
