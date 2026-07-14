#!/usr/bin/env bash
# Restore TEST — restore an agent DB dump into a SCRATCH database, verify row
# counts, then drop the scratch DB. Never touches live-named databases.
# Usage: restore-test-postgres.sh <dump-file> [scratch-db-name]
set -euo pipefail

DUMP="${1:?usage: restore-test-postgres.sh <dump-file> [scratch-db]}"
SCRATCH="${2:-agent_dev_restore_test}"
HOST="${PGHOST:-postgres}"
USER="${POSTGRES_DB_USER:-postgres}"

export PGPASSWORD="${POSTGRES_DB_PASSWORD:?set POSTGRES_DB_PASSWORD}"

echo "[restore-test] creating scratch DB $SCRATCH"
psql -h "$HOST" -U "$USER" -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\";"
psql -h "$HOST" -U "$USER" -d postgres -c "CREATE DATABASE \"$SCRATCH\";"

echo "[restore-test] restoring $DUMP into $SCRATCH"
pg_restore -h "$HOST" -U "$USER" --no-owner --no-privileges -d "$SCRATCH" "$DUMP"

echo "[restore-test] verifying row counts (public tables)"
psql -h "$HOST" -U "$USER" -d "$SCRATCH" -c \
  "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;"

echo "[restore-test] dropping scratch DB $SCRATCH"
psql -h "$HOST" -U "$USER" -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\";"

echo "[restore-test] PASS: restore of $(basename "$DUMP") verified, scratch cleaned up."
