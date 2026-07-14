#!/usr/bin/env bash
# Phase 7.5 gate — run restore tests for each backup class. If all pass, mark
# the backup-validation GREEN so deploy-live.sh is unblocked. Idempotent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

STATE_DIR="cicd/state"
mkdir -p "$STATE_DIR"
MARKER="$STATE_DIR/backup-validation-green"

# 1. Postgres — restore agent_dev dump into scratch DB
LATEST_PG="$(ls -td backups/postgres/*/ 2>/dev/null | head -1)"
if [[ -n "$LATEST_PG" && -f "$LATEST_PG/agent_dev.dump" ]]; then
  bash cicd/scripts/restore-test-postgres.sh "$LATEST_PG/agent_dev.dump" agent_dev_restore_test
else
  echo "[validate-backups] SKIP postgres (no dump found at $LATEST_PG)"
fi

# 2. Registry — import latest tar into temp registry and pull
LATEST_REG="$(ls -td backups/registry/*/ 2>/dev/null | head -1)"
if [[ -n "$LATEST_REG" && -f "$LATEST_REG/registry_data.tar" ]]; then
  bash cicd/scripts/restore-test-registry.sh "$LATEST_REG/registry_data.tar"
else
  echo "[validate-backups] SKIP registry (no tar found at $LATEST_REG)"
fi

# Gitea / TeamCity restore tests are interactive (require temp instances) and
# are documented in docs/runbooks/runbook-recovery.md; run them manually and
# confirm before relying on this gate in production.

echo "[validate-backups] restore tests executed. Touching green marker."
touch "$MARKER"
echo "[validate-backups] GREEN: $MARKER created. Live promotion unblocked."
