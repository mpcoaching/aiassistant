# Deployment

Desired state lives in Git. Deployments **reconcile** current → desired: Compose recreates only
changed services; named volumes persist. See also `docs/operations.md` and
`docs/runbooks/runbook-deployment.md`.

## Core invariants

- **Volumes = persistent state** — never deleted on deploy/upgrade.
- **Images = replaceable, immutable** — tagged by `<git-sha>`; never rebuilt during promotion.
- **Containers = disposable** — recreated from desired-state compose on every `up -d`.
- **Configuration = version-controlled** in Git.

## Five change classes

### 1. Application code change
Rebuild ONLY the affected service image, push, promote the SAME tag:
```
docker build -t registry.local.test/aiassistant/<svc>:<new-sha> -f agents/<svc>/Dockerfile agents/<svc>
docker push   registry.local.test/aiassistant/<svc>:<new-sha>
IMAGE_TAG=<new-sha> bash cicd/scripts/deploy-dev.sh
# ... integration tests ... approval ...
IMAGE_TAG=<new-sha> bash cicd/scripts/deploy-live.sh
```
Other services are untouched.

### 2. Infrastructure configuration change
Edit compose/config in Git, then converge only the affected service (named volumes persist):
```
docker compose -f infrastructure/compose.yml up -d nginx-proxy
```

### 3. Database schema change
Author a goose migration in `platform/db-setup/migrations`, require a **restore-tested backup**
(Phase 7.5) BEFORE any destructive migration, then apply via `migrate-dev` / `migrate-live`.
Rollback = down-migration to the previous known-good. Never hand-edit prod.

### 4. TeamCity Configuration-as-Code change
Edit `cicd/teamcity/settings.kts` → commit to Gitea → TeamCity detects the change from VCS and
**validates** (DSL compile + dry-run) before applying. A broken config is rejected; the previous
config stays active.

### 5. Platform service upgrade
Update the pinned image tag in `platform/compose.yml` (e.g. `postgres:16.x`), then:
```
docker compose -f platform/compose.yml up -d <svc>
```
Rely on healthchecks; rollback = revert the tag in Git + `up -d` the previous image.

## First-time bring-up order

```
infrastructure:up   # creates the 4 networks + control plane + registry
platform:up         # shared services + gateways
dev:up              # dev apps (or live:up for live)
```

## Promotion flow (dev → live, same digest)

```
push <sha> → Agent/Platform Tests → Coverage → Build → Push
  → Deploy Dev → Integration → [Phase 7.5 backups green] → Approval → Deploy Live
```
Verify dev & live run the identical digest:
```
docker inspect registry.local.test/aiassistant/workflow-runner:<sha>   # record digest
# after both deploys, compare digests
```
