#!/usr/bin/env bash
# Backup the private registry — tar the registry_data volume via a helper
# container. Non-destructive. Restores are validated by importing into a temp
# registry (see restore-test-registry.sh).
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-./backups/registry}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/$TS"
mkdir -p "$OUT"

echo "[backup-registry] taring registry_data -> $OUT/registry_data.tar"
docker run --rm -v infra_registry_data:/data -v "$PWD/$OUT":/backup alpine \
  tar -cf /backup/registry_data.tar -C /data .

echo "$TS" > "$OUT/manifest.txt"
echo "[backup-registry] done: $OUT"
