# Verification Plan — Multi-Tenant SaaS Deployment Platform

> Goal: prove the refactored platform (infra / platform / dev / live) actually runs,
> not just that the files parse. Produced because the prior implementation was
> validated only at the config level (`docker compose config`, `nginx -t`).

## Current status (already done, static only)
- `docker compose config` passes for `infrastructure/`, `platform/`, `environments/dev/`,
  `environments/live/`, `environments/dev/laptop.yml` — **zero warnings** with the real `.env`.
- `nginx -t` passes for `infrastructure/configs/nginx/nginx.conf`,
  `platform/configs/nginx/dev-gateway.conf`, `platform/configs/nginx/live-gateway.conf`.
- Image-tag existence (read-only): `postgres:16`, `redis:7-alpine`, `qdrant/qdrant:v1.13.4`,
  `rabbitmq:3-management-alpine`, `langfuse/langfuse:3` confirmed. **Remaining tags unconfirmed**
  (command timed out): `clickhouse/clickhouse-server:24-alpine`,
  `otel/opentelemetry-collector-contrib:0.114.0`, `openobserve/openobserve:0.14.1`,
  `gitea/gitea:1.22`, `registry:2`, `nginx:alpine`, `jetbrains/teamcity-server:2024.12`,
  `jetbrains/teamcity-agent:2024.12`, `ghcr.io/berriai/litellm:v1.62.3-stable`,
  `ghcr.io/kukymbr/goose-docker:1.24.0`.

## Risks (highest → lowest)
1. **Cross-project service-name DNS** (linchpin). The whole design assumes a container in one
   compose project resolves another project's service by bare name on a *shared* network
   (`dev-control-center-ui` on `dev-network` reached by `dev-platform-gateway` on `platform-network`;
   `dev-platform-gateway` reached by `nginx-proxy` on `infrastructure-network`). If Docker Compose
   only aliases by `<project>_<service>` and NOT the bare service name, every gateway/proxy lookup
   breaks. Must be proven with a 2-project test (Step V2).
2. **Guessed image tags** (Step V1). Any wrong tag → `pull` fails → `up` aborts.
3. **TeamCity Kotlin DSL compile** (Step V6). `settings.kts` imports
   `jetbrains.buildServer.configs.kotlin.*` and uses `sequential {}` / `Type.COMPOSITE`. The only
   true validation is loading it into a TeamCity 2024.12 server; the import/version must match.
4. **`env_file` relative paths** at `up` time: platform `../.env`, env `../../.env`, mounts
   `../../infra/wait_for.py`. Verified by `config`, but `up` resolves from CWD — confirm.
5. **DB bootstrap/migrations** actually create `agent_dev`/`agent_live` and apply goose files
   (Step V4).
6. **Registry TLS trust** on the host Docker daemon (`cicd/...` pulls run in host context) — needs
   the `local.test` CA installed or `insecure-registries` (Step V5).

## Validation plan (ordered, cheapest first)

### V1 — Confirm every pinned image exists (read-only, fast)
For each tag in the 4 composes + gateways run `docker manifest inspect <tag>` (no layer download).
Any `MISS` → fix the tag in the owning compose (then re-pin to `@sha256` per ADR-006).
Tags: postgres:16, redis:7-alpine, qdrant/qdrant:v1.13.4, rabbitmq:3-management-alpine,
langfuse/langfuse:3, clickhouse/clickhouse-server:24-alpine,
otel/opentelemetry-collector-contrib:0.114.0, openobserve/openobserve:0.14.1, gitea/gitea:1.22,
registry:2, nginx:alpine, jetbrains/teamcity-server:2024.12, jetbrains/teamcity-agent:2024.12,
ghcr.io/berriai/litellm:v1.62.3-stable, ghcr.io/kukymbr/goose-docker:1.24.0.

### V2 — Prove cross-project DNS (the linchpin; tiny, no real services)
Create a throwaway 2-project test:
- `projA/compose.yml`: network `xnet` (real, `name: xnet`), service `a` (nginx:alpine).
- `projB/compose.yml`: network `xnet` (`external: true`, `name: xnet`), service `b` (busybox).
`docker compose -f projB/compose.yml run b getent hosts a` (or `nslookup a`). If it resolves,
the gateway design is sound. Tear down after.

### V3 — Bring up infra + platform, watch logs
`docker compose -f infrastructure/compose.yml up -d` then
`docker compose -f platform/compose.yml up -d`.
- `docker network ls --filter name=network` → 4 networks present.
- `docker compose -f infrastructure/compose.yml logs -f nginx-proxy dns` clean.
- `curl -fsS https://gitea.local.test` and `https://teamcity.local.test` → 200
  (requires host resolver → dnsmasq; if `systemd-resolved` owns :53, stop it first).

### V4 — DB bootstrap + migrations
- Exec into `postgres`; `\l` shows `agent_dev`, `agent_live`, `langgraph_dev/_live`, `litellm`.
- `\du` shows `agent_dev_user` owning only `agent_dev` (isolation check).
- `migrate-dev`/`migrate-live` exit 0; `agent_dev` has the `workflow_engine` tables.

### V5 — Registry round-trip
`docker tag busybox registry.local.test/aiassistant/busybox:test`
→ `docker push` (login with `htpasswd` creds) → `docker pull`. Unauthenticated push rejected.

### V6 — TeamCity DSL compile
After `infra:up`, in TeamCity UI enable Versioned Settings → Gitea `cicd/teamcity`. Observe the
"Settings" page for a parse error. Fix any DSL/version mismatch in `settings.kts`.

### V7 — Build + deploy dev, end-to-end
Build the 3 app images, tag `<sha>`, push. `IMAGE_TAG=<sha> bash cicd/scripts/deploy-dev.sh`.
`curl -fsS https://agent.dev.local.test` → 200; same for `api.dev.local.test`,
`langgraph.dev.local.test`. **Isolation proof:** `docker compose -f environments/dev/compose.yml
run dev-workflow-engine getent hosts live-platform-gateway` → should FAIL (different network).

### V8 — Backup / restore gate
`bash cicd/scripts/backup-all.sh`; `bash cicd/scripts/validate-backups.sh` → creates
`cicd/state/backup-validation-green`; `deploy-live.sh` then proceeds.

## Open questions / decisions needed
- **Scope of execution:** static plan only (current mode), or switch to code mode to actually run
  V1–V8? V2/V3/V5/V7 require pulling multiple GB of images and running Postgres/TeamCity — slow and
  mutating.
- **Docker daemon trust for registry:** install `local.test` CA into `/etc/docker/certs.d`, or add
  `registry.local.test` to `insecure-registries`? (documented trade-off in `docs/networking.md`).
- **`litellm`/`goose` tags:** if V1 shows them missing, accept a corrected version or pin to digest.
