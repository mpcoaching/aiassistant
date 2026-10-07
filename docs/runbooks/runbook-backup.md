# Runbook — Backup

## Overview

Run this from the repo root on the **host** (`agent99@192.168.1.238`) or via `make remote-backup` from any machine that can SSH to it. Backups are stored under `./backups/` and are timestamped.

## Prerequisites

- SSH access to `agent99@192.168.1.238` with key auth
- `.env` present at repo root on the remote host
- Docker running; all service containers up
- Sufficient disk space on the remote host (current stack ≈ 20–70 GB)

## Automated backup

```bash
make remote-backup
```

This runs `scripts/backup.sh` over SSH and produces timestamped artifacts in `./backups/`:

| Artifact | Content |
|---|---|
| `config-backup-<ts>.tar.gz` | `.env`, compose files, configs, makefile |
| `postgres-all-dbs-<ts>.sql` | `pg_dumpall` of all PostgreSQL databases |
| `clickhouse-backup-<ts>.tar.gz` | Tar of `/var/lib/clickhouse` (ignore-failed-read) |
| `redis-dump-<ts>.rdb` | Primary Redis `dump.rdb` |
| `redis-agents-dump-<ts>.rdb` | Agents Redis `dump.rdb` |
| `volume-<name>-<ts>.tar.gz` | Tar of each Docker volume's `_data` directory |
| `deployment-state-*.txt` | Containers, volumes, networks, images, git HEAD |

## Manual backup (per-component)

If a single component needs re-backing up without the full stack:

```bash
# PostgreSQL
ssh agent99@192.168.1.238 "docker exec platform-postgres-1 pg_dumpall -U postgres > ./backups/postgres-all-dbs.sql"

# Redis
ssh agent99@192.168.1.238 "docker exec platform-redis-1 redis-cli BGSAVE && docker cp platform-redis-1:/data/dump.rdb ./backups/redis-dump.rdb"

# ClickHouse
ssh agent99@192.168.1.238 "docker exec platform-clickhouse-1 tar -czf /tmp/clickhouse-backup.tar.gz --ignore-failed-read -C /var/lib/clickhouse ."
ssh agent99@192.168.1.238 "docker cp platform-clickhouse-1:/tmp/clickhouse-backup.tar.gz ./backups/clickhouse-backup.tar.gz"

# Single volume
VOLUME=platform_n8n_data
ssh agent99@192.168.1.238 "docker run --rm -v ${VOLUME}:/data -v \$(pwd)/backups:/backup alpine tar -czf /backup/${VOLUME}.tar.gz -C /data ."

# Config only
ssh agent99@192.168.1.238 "cd /home/agent99/projects/aiassistant && tar -czf ./backups/config-backup.tar.gz .env .env.template platform/compose.yml platform/compose.*.yml infrastructure/compose.yml infrastructure/compose.*.yml cms/docker-compose.yml cms/docker-compose.*.yml makefile infrastructure/configs/ platform/configs/ contracts/"
```

## Retention

- Backups are **not** automatically pruned.
- Off-host copy should be taken before any destructive operation (upgrade, rebuild).
- Consider adding a cron job to rsync `./backups/` to a remote location nightly.

## Verification

```bash
ls -lah /home/agent99/projects/aiassistant/backups/
# spot-check
tar -tzf /home/agent99/projects/aiassistant/backups/config-backup-*.tar.gz | head
gzip -t /home/agent99/projects/aiassistant/backups/volume-*.tar.gz
```

## Restore (tested workflow)

1. Copy the relevant backup file(s) to the target host.
2. For PostgreSQL: create the target DB, then `psql -f postgres-all-dbs.sql`.
3. For Redis: stop the Redis container, replace `dump.rdb`, start.
4. For volumes: stop the target container, `docker run --rm -v <new-vol>:/data -v /host/backups:/backup alpine tar -xzf /backup/volume-<name>.tar.gz -C /data`, start container.
5. For configs: extract `config-backup-*.tar.gz` over the repo root and review diffs before committing.

## Notes

- `.env` is **not** in Git; it must be backed up separately (included in `config-backup-*.tar.gz`).
- Running services are **not** stopped during backup; database dumps are taken live.
- ClickHouse does not have an online `BACKUP` engine available in the current image; we tar the data directory with `--ignore-failed-read` because parts may be in use by the running process.
- If a backup fails partway, re-run the script; it creates new timestamped files and does not delete prior ones.
