#!/usr/bin/env bash
# Backup Gitea — `gitea dump` into a timestamped directory. Restore is tested
# by importing into a TEMP Gitea instance and verifying a repo + webhook exist.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-./backups/gitea}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/$TS"
mkdir -p "$OUT"

echo "[backup-gitea] gitea dump -> $OUT"
docker exec infra_gitea sh -c "cd /data && gitea dump -t --file /data/gitea-dump.zip" || \
  docker exec infra_gitea sh -c "cd /tmp && gitea dump -t --file /tmp/gitea-dump.zip"
docker cp infra_gitea:/data/gitea-dump.zip "$OUT/" 2>/dev/null || \
  docker cp infra_gitea:/tmp/gitea-dump.zip "$OUT/"

echo "$TS" > "$OUT/manifest.txt"
echo "[backup-gitea] done: $OUT"
