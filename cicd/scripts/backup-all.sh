#!/usr/bin/env bash
# Backup ALL platform state (Postgres, registry, Gitea, TeamCity) into
# timestamped directories under ./backups. Non-destructive.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

bash cicd/scripts/backup-postgres.sh
bash cicd/scripts/backup-registry.sh
bash cicd/scripts/backup-gitea.sh
bash cicd/scripts/backup-teamcity.sh

echo "[backup-all] complete. Config state is also captured by git tagging at promotion."
