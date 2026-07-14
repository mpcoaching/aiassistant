# Runbook — Shutdown

Stop stacks in reverse order. **Named volumes are preserved** (no `-v`), so state survives a restart.

## Graceful stop
```bash
# Stop app environments first
npm run dev:down      # docker compose -f environments/dev/compose.yml down
npm run live:down     # docker compose -f environments/live/compose.yml down

# Stop platform shared services
npm run platform:down # docker compose -f platform/compose.yml down

# Stop infrastructure last (DNS/nginx/CI/registry)
npm run infra:down    # docker compose -f infrastructure/compose.yml down
```

## Full wipe (DESTRUCTIVE — only for rebuilds)
Removes containers AND all named volumes (Postgres, registry, Gitea, TeamCity, …). Take a backup
first (`bash cicd/scripts/backup-all.sh`).
```bash
docker compose -f environments/dev/compose.yml  down -v
docker compose -f environments/live/compose.yml down -v
docker compose -f platform/compose.yml          down -v
docker compose -f infrastructure/compose.yml    down -v
docker network rm infrastructure-network platform-network dev-network live-network
```

## Notes
- Stopping infrastructure removes DNS; `*.local.test` resolution stops until it is back up.
- TeamCity agent uses the host Docker socket; it stops with the infrastructure stack.
