# CI/CD

Continuous delivery is provided by **TeamCity Configuration-as-Code** (Kotlin DSL in Gitea) with a
self-hosted agent that uses the host Docker daemon (Option A). Gitea is the VCS source of truth.

## Topology

```
Gitea (ai/aiassistant)  ──webhook──▶  TeamCity server  ──schedules──▶  TeamCity agent
   (VCS root)                        (reads cicd/teamcity)              (host docker.sock)
```

- **Versioned Settings:** TeamCity reads `cicd/teamcity/settings.kts` from Gitea. A broken config is
  rejected at validate time; the previous config stays active.
- **Agent (Option A):** mounts host `/var/run/docker.sock` (near-privileged) — acceptable on a single
  trusted host. Option B (rootless dind) is recorded as future hardening (ADR-002).
- **Registry auth:** TeamCity password params `REGISTRY_USER` / `REGISTRY_PASSWORD`; the push step
  logs in via `echo "$REGISTRY_PASSWORD" | docker login ... --password-stdin` before pushing.

## Build chain (10 configs, snapshot dependencies)

```
1 Agent Unit Tests ─▶ 2 Platform Unit Tests ─▶ 3 Coverage Verification
  ─▶ 4 Docker Image Build ─▶ 5 Push Image To Registry
  ─▶ 6 Deploy Development ─▶ 7 Integration Tests
  ─▶ 8 Promotion Approval (manual) ─▶ 9 Deploy Live ─▶ 10 Rollback (manual, on demand)
```

- **1 Agent Unit Tests** — `pytest` (`agents/workflow-runner`) + `vitest` (`agents/control-center-ui`).
- **2 Platform Unit Tests** — extensible placeholder for `platform/` service tests.
- **3 Coverage Verification** — `cicd/coverage/check-coverage.py` ratchet vs baseline; **fails on
  decrease** (`cicd/coverage/coverage.baseline.json`).
- **4 Docker Image Build** — build `workflow-runner` / `control-center-ui` / `langgraph`, tag `<git-sha>`.
- **5 Push Image To Registry** — `docker push registry.local.test/aiassistant/<svc>:<git-sha>`.
- **6 Deploy Development** — `cicd/scripts/deploy-dev.sh` (login + pull + `up -d`).
- **7 Integration Tests** — `cicd/scripts/integration-tests.sh` against dev.
- **8 Promotion Approval** — **manual gate**; requires Phase 7.5 backup validation green.
- **9 Deploy Live** — `cicd/scripts/deploy-live.sh` deploys the **same** `<git-sha>`.
- **10 Rollback** — `cicd/scripts/rollback.sh <prior-tag>`.

## Quality gate

- Coverage ratchet must pass (no regression).
- Integration tests green.
- Phase 7.5 restore tests green (marker `cicd/state/backup-validation-green`).
- Manual promotion approval given.
- `validate-promotion.sh` rejects any `latest` / `build:` reference for promoted services.

A failing test (e.g. drop coverage) blocks promotion automatically.

## Scripts

| Script | Purpose |
|---|---|
| `cicd/scripts/deploy-dev.sh` | login + pull + `up -d` dev from registry |
| `cicd/scripts/deploy-live.sh` | deploy live (same tag); blocked until backup-validation green |
| `cicd/scripts/rollback.sh` | redeploy a prior immutable tag |
| `cicd/scripts/integration-tests.sh` | smoke tests against dev |
| `cicd/scripts/validate-promotion.sh` | reject mutable image references |
| `cicd/scripts/gitea-seed.sh` | one-time Gitea org/repo/deploy-key/webhook bootstrap |
| `cicd/coverage/check-coverage.py` | ratcheting coverage gate |

## Bootstrap

1. Bring up infrastructure + platform (`infrastructure:up`, `platform:up`).
2. `bash cicd/scripts/gitea-seed.sh` to create `ai/aiassistant` + webhook.
3. In TeamCity, enable Versioned Settings → point at Gitea `cicd/teamcity`. The 10 build configs
   load automatically.
