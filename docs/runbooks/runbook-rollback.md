# Runbook — Rollback

Rollback redeploys a **prior immutable tag**. No rebuild, no data loss (volumes persist).

## Trigger
Use after a failed deployment or regression detected in Live. Invoke the TeamCity "Rollback" build
config (BC10) or run manually.

## Manual rollback
```bash
export REGISTRY_URL=registry.local.test/aiassistant
echo "$REGISTRY_PASSWORD" | docker login "$REGISTRY_URL" -u "$REGISTRY_USER" --password-stdin

# Roll back Live to a known-good tag (images already in the registry)
bash cicd/scripts/rollback.sh <prior-git-sha> live

# or Dev
bash cicd/scripts/rollback.sh <prior-git-sha> dev
```

`rollback.sh` pulls the prior tag and runs `up -d`, reconverging the environment to that digest.

## Verify
```bash
docker compose -f environments/live/compose.yml images
curl -fsS https://agent.live.local.test
```

## Database rollback
If a destructive migration caused the failure, apply the corresponding goose down-migration:
```bash
# example (dev): run goose down against agent_dev
docker compose -f platform/compose.yml run --rm \
  -e GOOSE_DBSTRING="postgres://${AGENT_DEV_DB_USER}:${AGENT_DEV_DB_PASSWORD}@postgres:5432/${AGENT_DEV_DB_NAME}?sslmode=disable" \
  migrate-dev down
```
Always restore from a tested backup (`runbook-recovery.md`) if data is corrupted, not just migrate down.

## Notes
- Rollback changes only the image tag; configuration in Git should also be reverted to the prior SHA
  if the bad deploy included config changes.
- Because promotion is immutable, the prior image is guaranteed present in the registry.
