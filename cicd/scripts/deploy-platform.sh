#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Host-side deployment of the n8n service.
#
#   Usage: deploy-platform.sh <commit-sha>
#
# INVOKED BY: the CI `deploy-platform` step, which runs this script inside a
# container on the deployment host, AFTER the calling command has already:
#   1. bind-mounted the authoritative checkout at its real host path
#      (DEPLOY_DIR), so the relative custom-nodes bind resolves to real files
#   2. verified the tracked working tree is clean (never `git reset --hard`)
#   3. fetched origin and verified the EXACT commit SHA exists
#   4. checked out EXACTLY that SHA (detached HEAD)
#
# Because steps 1-4 run BEFORE this script, a host on ANY prior commit can
# deploy a NEWER commit that introduces this script: this script is never
# required to pre-exist on the host.
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
DEPLOY_DIR="${DEPLOY_DIR:-/home/martinp/Documents/projects/aiassistant}"

if [ -z "$COMMIT_SHA" ]; then
  echo "ERROR: missing commit SHA argument." >&2
  echo "       Usage: $0 <commit-sha>" >&2
  exit 1
fi

cd "$DEPLOY_DIR"

# Defensive: confirm we are exactly on the requested commit before converging.
# Resolve the argument to a full object id first so an abbreviated SHA is
# accepted and compared correctly.
HEAD_SHA="$(git rev-parse HEAD)"
WANTED_SHA="$(git rev-parse "${COMMIT_SHA}^{commit}")"
if [ "$HEAD_SHA" != "$WANTED_SHA" ]; then
  echo "ERROR: HEAD ($HEAD_SHA) != requested SHA ($WANTED_SHA). Aborting deploy." >&2
  exit 1
fi

# --- Converge ONLY n8n -------------------------------------------------------
# --force-recreate ensures the n8n container is recreated and re-reads its
# bind mount (../custom-nodes:/home/node/.n8n/custom) so a custom-node change
# is loaded at startup (n8n reads N8N_CUSTOM_EXTENSIONS only at startup, and a
# custom-nodes-only change produces no compose config drift to trigger a
# recreate on its own). No --pull / --build is used, so the n8n image tag is
# unchanged and no image is rebuilt.
#
# The bind source is relative to THIS file's compose file (platform/), so it
# resolves to the repository root's custom-nodes. This script must therefore
# run from the authoritative checkout that holds those files.
docker compose \
  -f platform/compose.yml \
  --env-file .env \
  up -d --force-recreate n8n

echo ">> n8n converged at ${HEAD_SHA}"
echo ">> Platform deploy complete."
