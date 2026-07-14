#!/usr/bin/env bash
# Backup Postgres — pg_dump per database into a timestamped directory.
# Non-destructive; never drops live databases. Run from a host with psql +
# network access to postgres:5432 (e.g. via the infra network).
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-./backups/postgres}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/$TS"
mkdir -p "$OUT"

DBS=("${@:-agent_dev agent_live langgraph_dev langgraph_live litellm langfuse n8n teamcity openobserve openhands manifest opencode}")

echo "[backup-postgres] dumping: ${DBS[*]} -> $OUT"
for db in "${DBS[@]}"; do
  echo "  dumping $db ..."
  PGPASSWORD="${POSTGRES_DB_PASSWORD:?set POSTGRES_DB_PASSWORD}" \
    pg_dump -h "${PGHOST:-postgres}" -U "${POSTGRES_DB_USER:-postgres}" -Fc -f "$OUT/$db.dump" "$db"
done
echo "$TS" > "$OUT/manifest.txt"
echo "[backup-postgres] done: $OUT"
