#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-agent99@192.168.1.238}"
REMOTE_DIR="${REMOTE_DIR:-/home/agent99/projects/aiassistant}"
BACKUP_DIR="${REMOTE_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

info() { echo "[backup] $*"; }

info "Recording deployment state..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  mkdir -p ${BACKUP_DIR}
  cd ${REMOTE_DIR}
  git rev-parse HEAD > ${BACKUP_DIR}/git-head.txt 2>/dev/null || echo 'no-git' > ${BACKUP_DIR}/git-head.txt
  git status --porcelain > ${BACKUP_DIR}/git-status.txt 2>/dev/null || true
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' > ${BACKUP_DIR}/deployment-state-containers.txt
  docker volume ls --format 'table {{.Name}}\t{{.Driver}}' > ${BACKUP_DIR}/deployment-state-volumes.txt
  docker network ls --format 'table {{.Name}}\t{{.Driver}}' > ${BACKUP_DIR}/deployment-state-networks.txt
  docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}' > ${BACKUP_DIR}/deployment-state-images.txt
"

info "Backing up configuration..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  cd ${REMOTE_DIR}
  tar --ignore-failed-read -czf ${BACKUP_DIR}/config-backup-${TIMESTAMP}.tar.gz \
    .env .env.template \
    platform/compose.yml platform/compose.*.yml \
    infrastructure/compose.yml infrastructure/compose.*.yml \
    cms/docker-compose.yml cms/docker-compose.*.yml \
    makefile \
    infrastructure/configs/ platform/configs/ contracts/
"

info "Dumping PostgreSQL..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  docker exec platform-postgres-1 pg_dumpall -U postgres > ${BACKUP_DIR}/postgres-all-dbs-${TIMESTAMP}.sql
"

info "Backing up ClickHouse..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  docker exec platform-clickhouse-1 tar -czf /tmp/clickhouse-backup-${TIMESTAMP}.tar.gz --ignore-failed-read -C /var/lib/clickhouse . || true
  docker cp platform-clickhouse-1:/tmp/clickhouse-backup-${TIMESTAMP}.tar.gz ${BACKUP_DIR}/clickhouse-backup-${TIMESTAMP}.tar.gz || true
"

info "Dumping Redis..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  docker exec platform-redis-1 redis-cli BGSAVE
  docker cp platform-redis-1:/data/dump.rdb ${BACKUP_DIR}/redis-dump-${TIMESTAMP}.rdb
  docker exec platform-redis-agents-1 redis-cli BGSAVE
  docker cp platform-redis-agents-1:/data/dump.rdb ${BACKUP_DIR}/redis-agents-dump-${TIMESTAMP}.rdb
"

info "Archiving Docker volumes..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "BACKUP_DIR='${BACKUP_DIR}' TIMESTAMP='${TIMESTAMP}' bash -s" <<'REMOTE_EOF'
VOLUMES=(
  platform_langfuse_data
  platform_postgres_db
  platform_rabbitmq_data
  platform_langfuse_redis_data
  platform_redis_agents_data
  platform_qdrant_data
  platform_openobserve_storage
  platform_clickhouse_data
  platform_n8n_data
  infrastructure_woodpecker-agent-config
  infrastructure_registry_data
  infrastructure_woodpecker-server-data
  infrastructure_redis_data
  infrastructure_gitea_data
)
for vol in "${VOLUMES[@]}"; do
  docker run --rm -v "${vol}:/data" -v "${BACKUP_DIR}:/backup" alpine tar -czf "/backup/volume-${vol}-${TIMESTAMP}.tar.gz" -C /data . && echo "[backup] ${vol} done"
done
REMOTE_EOF

info "Verifying backups..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" "
  ls -lah ${BACKUP_DIR}/*${TIMESTAMP}* | wc -l
  du -sh ${BACKUP_DIR}/*${TIMESTAMP}*
"

info "Backup complete: ${BACKUP_DIR}"
