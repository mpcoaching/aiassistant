#!/usr/bin/env bash
# Backup TeamCity — snapshot the teamcity_data volume (server datadir) and
# teamcity_logs. Settings-as-code live in Gitea (cicd/teamcity), so restoring
# the volume + repointing to VCS restores the server config.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-./backups/teamcity}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/$TS"
mkdir -p "$OUT"

echo "[backup-teamcity] taring teamcity_data + teamcity_logs -> $OUT"
docker run --rm -v infra_teamcity_data:/data -v "$PWD/$OUT":/backup alpine \
  tar -cf /backup/teamcity_data.tar -C /data .
docker run --rm -v infra_teamcity_logs:/logs -v "$PWD/$OUT":/backup alpine \
  tar -cf /backup/teamcity_logs.tar -C /logs .

echo "$TS" > "$OUT/manifest.txt"
echo "[backup-teamcity] done: $OUT"
