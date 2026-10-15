# Runbook — Deployment

Promotes an immutable `<git-sha>` from Dev → Live. Desired state lives in Git; `up -d` reconciles.

## Normal deployment (via TeamCity)
The build chain (see `docs/ci-cd.md`) handles build → push → deploy-dev → integration → approval →
deploy-live. Manual steps only if running outside TeamCity.

## Manual deployment
```bash
export IMAGE_TAG=<git-sha>
export REGISTRY_URL=registry.local.test/aiassistant

# login once
echo "$REGISTRY_PASSWORD" | docker login "$REGISTRY_URL" -u "$REGISTRY_USER" --password-stdin

# Dev
bash cicd/scripts/deploy-dev.sh

# ... run integration tests ...
bash cicd/scripts/integration-tests.sh

# (first live only) confirm Phase 7.5 backups are green
bash cicd/scripts/validate-backups.sh

# Live — same tag
bash cicd/scripts/deploy-live.sh
```

## Verify promotion integrity (dev & live identical digest)
```bash
docker inspect registry.local.test/aiassistant/workflow-runner:$IMAGE_TAG | grep -m1 RepoDigests
# after both deploys:
docker compose -f environments/dev/compose.yml  images workflow-runner
docker compose -f environments/live/compose.yml images workflow-runner
# digests must match
```

## Configuration-only change (no image rebuild)
Edit the compose/config in Git, then converge only the affected service:
```bash
docker compose -f infrastructure/compose.yml up -d nginx-proxy
```

## Troubleshooting
- `validate-promotion.sh` fails → a service uses `latest`/`build:`. Fix the tag, re-push.
- `deploy-live.sh` blocked → `cicd/state/backup-validation-green` missing. Run `validate-backups.sh`
  after a successful restore test.
- App can't reach Postgres → confirm it points at `<env>-platform-gateway:5432`, not `postgres:5432`.
