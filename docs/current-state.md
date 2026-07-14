# Current State

> Documented as the baseline for the Multi-Tenant-Ready SaaS Deployment Platform refactor
> (see `.kilo/plans/1783998200920-saas-deployment-platform-plan.md`). This file captures the
> stack **as it exists today** before any restructuring. It must match `docker compose config`
> output of the legacy files.

Last reconciled against the legacy files:
`docker-compose.platform.yml`, `docker-compose.yml`, `docker-compose.dev.yml`, and the
`ai-assistant-infra/`, `infra/`, `agentic/src/`, `agents/` directories.

---

## 1. Compose topology (legacy)

There are **three** compose files today, all run as separate Docker Compose projects in the
same working directory:

| File | Role | Start order |
|---|---|---|
| `docker-compose.platform.yml` | Tier-0 platform substrate + CI stack (always-on, shared) | **First** |
| `docker-compose.yml` | Agentic dev + live app tiers (optional profiles) | After platform |
| `docker-compose.dev.yml` | Laptop-only DinD workspace overlay (merged with `docker-compose.yml`) | Laptop only |

The platform file **owns** two networks, `ai_net` and `monitoring-net`, and declares them as
real bridge networks. The app file and dev overlay declare them as `external: true`.

### Critical quirk (untangled by the refactor)
`docker-compose.dev.yml` **redefines** `ai_net`/`monitoring-net` as local bridge networks with
explicit names so that a single-service `docker compose -f docker-compose.yml -f docker-compose.dev.yml up <svc>`
works on a laptop without the full platform running. This means network ownership is split and
depends on which overlay is active — the refactor gives each of the four new networks a single owner.

---

## 2. Networks (current)

| Network | Driver | Owner | Members |
|---|---|---|---|
| `ai_net` | bridge | `docker-compose.platform.yml` | nginx-proxy, dns, postgres, qdrant, rabbitmq, redis-agents, langfuse/clickhouse/otel/openobserve (via monitoring-net), gitea, teamcity-server, teamcity-agent, **and all app + optional containers** |
| `monitoring-net` | bridge | `docker-compose.platform.yml` | nginx-proxy, dns, redis (langfuse), clickhouse, langfuse, otel-collector, openobserve, n8n, langgraph, dev-langgraph, teamcity-server, teamcity-agent |

**Every app container attaches to `ai_net`.** There is **no** dev/live network separation today:
`dev-workflow-engine`, `workflow-engine`, `dev-langgraph`, `langgraph`, `dev-litellm`, `litellm`
all share the same `ai_net` and `monitoring-net`. App-to-app and app-to-platform traffic is fully
open across every environment.

---

## 3. Host ports (published)

| Host port | Service | Notes |
|---|---|---|
| `80` / `443` | nginx-proxy | TLS via `ai-assistant-infra/configs/nginx/certs/local.test.crt` |
| `53/udp` + `53/tcp` | dns (dnsmasq) | requires `CAP_NET_ADMIN`; may conflict with `systemd-resolved` on Ubuntu/WSL2 |
| `15672` | rabbitmq management | published |
| `8081` | (reserved) | published |
| (in-container only) | qdrant 6333/6334, litellm 4000, langfuse 3000, otel 4318, openobserve 5080, gitea 3000, teamcity 8111, control-center-ui 80, workflow-engine 8000, langgraph 8000 | reached via nginx or `ai_net` |

There is **no** explicit `*.dev.local.test` / `*.live.local.test` routing today. nginx routes a
flat set of `.local.test` hostnames (including `control-center.local.test`, `workflow-engine.local.test`,
`langgraph.local.test`, `litellm.local.test`, `gitea.local.test`, `teamcity.local.test`, `lf.local.test`,
`oo.local.test`, `otel.local.test`, `qdrant.local.test`).

### Known nginx defect (fixed by refactor)
`ai-assistant-infra/configs/nginx/nginx.conf` contains a **duplicate** HTTP server block for
`qdrant.local.test` (lines 151–179), followed by a separate `listen 6334` / `listen 443 ssl`
server block. The refactor rewrites this config with explicit upstreams and removes the duplication.

---

## 4. Services by stack

### Platform substrate (`docker-compose.platform.yml`)
- **nginx-proxy** (`nginx:alpine`) — client entry; hot-reloads its own config via an md5-loop.
- **dns** (`strm/dnsmasq`) — wildcard `*.local.test → 127.0.0.1`.
- **postgres** (`postgres:16`) — shared Postgres; superuser `postgres` from `.env`.
- **db-bootstrapper** (`python:3.11-alpine`) — runs `ai-assistant-infra/db-setup/bootstrap.sh`
  (envsubst over 001/002/003 SQL) to create per-service DBs + users + grants.
- **migrate** (`ghcr.io/kukymbr/goose-docker:latest` — **moving tag**, pinned in refactor) — goose
  migrations from `ai-assistant-infra/migrations`. **Moving `latest` tag flagged for immutability.**
- **qdrant** (`qdrant/qdrant:latest`) — vector store; api key from `QDRANT_KEY`.
- **rabbitmq** (`rabbitmq:3-management-alpine`) — message bus (guest/guest).
- **redis-agents** (`redis:7-alpine`) — shared cache for litellm/langgraph.
- **langfuse** (`langfuse/langfuse:3`) + **redis** (langfuse) + **clickhouse** (`clickhouse/clickhouse-server:24-alpine`) — LLM observability.
- **otel-collector** (`otel/opentelemetry-collector-contrib:latest`) — OTLP → OpenObserve.
- **openobserve** (`openobserve/openobserve:latest`) — logs/traces UI.
- **gitea** (`gitea/gitea:latest`) — git source of truth (sqlite3).
- **teamcity-server** (`jetbrains/teamcity-server:latest`) — backed by shared Postgres `teamcity` DB.
- **teamcity-agent** (`jetbrains/teamcity-agent:latest`) — **`privileged: true`**, mounts host
  `/var/run/docker.sock` (Option A, recorded as a security boundary decision).
- *Disabled by default:* `minio`, `ollama`, `n8n`.

### Agentic app tiers (`docker-compose.yml`)
- **LIVE:** `control-center-ui` (nginx, `live` target), `workflow-engine` (uvicorn), `langgraph`,
  `litellm` (`ghcr.io/berriai/litellm:main-latest` — **moving tag**, pinned in refactor).
- **DEV:** `dev-controller` (`node:20-alpine`, runs on `:8443` directly, NOT behind nginx),
  `dev-workflow-engine`, `dev-langgraph`, `dev-litellm` (**separate per-env litellm** today).

**Dev UI is NOT behind nginx today.** `dev-controller` runs on `:8443` and is reached directly. The
refactor adds explicit `*.dev.local.test` routing.

### Laptop overlay (`docker-compose.dev.yml`)
- `workspace` (`.devcontainer/Dockerfile`) + `docker-dind` (`docker:dind`, `privileged: true`) —
  DinD workspace for one-service-at-a-time development. The refactor re-evaluates this pattern
  under the four-network model (see `environments/dev/laptop.yml`).

---

## 5. Volumes (named)

`postgres_db`, `qdrant_data`, `rabbitmq_data`, `redis_agents_data`, `langfuse_redis_data`,
`langfuse_data`, `clickhouse_data`, `openobserve_storage`, `minio_data`, `ollama_models`,
`n8n_data`, `gitea_data`, `teamcity_data`, `teamcity_logs`, `teamcity_agent_conf`,

All are declared in `docker-compose.platform.yml`. There is no cross-file `external` volume sharing
today because everything runs under that one project.

---

## 6. DNS entries (`.local.test → host`)

dnsmasq maps **all** `*.local.test` to `127.0.0.1` (host). There are no explicit `dev`/`live`
entries. The refactor adds explicit `address=/.dev.local.test/...` and `address=/.live.local.test/...`
(or documents that the wildcard already covers them).

---

## 7. Credential locations

- **`.env`** (and `.env.template`) — single source of truth for all secrets and DB names. Contains
  real API keys today (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GITHUB_PAT`,
  LiteLLM master/salt, etc.). The refactor keeps `.env` out of git history hygiene and renames the
  DB convention to `agent_dev`/`agent_live`.
- **Gitea deploy key** — `~/.ssh/gitea_deploy.pub`, installed by `infra/ci/gitea-seed.sh`.
- **TeamCity Postgres** — `TEAMCITY_DB_*` in `.env`; JDBC via `TEAMCITY_SERVER_OPTS`.
- **Windows path leak** — `.env` has `AIASSIST_PATH=C:/Users/...` which breaks inside WSL2
  containers; removed in the refactor.

---

## 8. Intra-stack dependencies

```
db-bootstrapper  →  migrate  →  (langfuse, openobserve depend_on migrate)
postgres (healthy)  →  teamcity-server
teamcity-server  →  teamcity-agent
```

Cross-project `depends_on` is **unsupported** (platform vs app are separate compose projects), so
app containers use a `wait_for.py` entrypoint loop to block on `postgres:5432`, `rabbitmq:5672`,
`langgraph:8000`, `redis-agents:6379`. `infra/wait_for.py` is volume-mounted into `workflow-engine`,
`dev-workflow-engine`, `litellm`, `dev-litellm`.

---

## 9. CI / CD (current)

- **TeamCity** is configured **manually** in the UI (3 build configs: BC1 Test&Build, BC2 Promote→Dev,
  BC3 Promote→Live). The 3-BC model is documented in `infra/ci/teamcity-build-configs.md` and is
  superseded by Kotlin-DSL CaaS in the refactor.
- **Gitea** is seeded by `infra/ci/gitea-seed.sh` (org `ai` / repo `aiassistant`, deploy key, webhook).
- **Coverage ratchet:** `infra/ci/check-coverage.py` + `infra/ci/coverage.baseline.json`
  (all zeros today). Reused verbatim in `cicd/coverage/`.
- **GitHub Actions** `.github/workflows/control-center-ui.yml` is **deprecated** and intentionally
  a no-op; retained as an optional mirror.
- **Images use moving tags / `build:` everywhere** — nothing is promoted via an immutable registry
  today. The refactor introduces `registry.local.test` and `<git-sha>` immutability.

---

## 10. Image / promotion model (current = none)

Today each environment is built locally with `build:` and `docker compose up -d --build`. There is
**no** private registry, **no** immutable tag, and **no** promotion of the same artifact between dev
and live. Live and dev build the same `Dockerfile` contexts independently. The refactor (§3) changes
this to a single immutable `registry.local/aiassistant/<svc>:<git-sha>` promoted identically to both.

---

## 11. Known issues carried into the refactor

1. Flat shared `ai_net` — no environment isolation (Phase 7 fixes).
2. Duplicate nginx `qdrant.local.test` server block (rewrite fixes).
3. `litellm` moving tag; `migrate` moving `latest` tag (immutability fixes).
5. `AIASSIST_PATH` Windows path in `.env` (removed).
6. DB naming `aiassistant_dev`/`aiassistant_live` vs plan's `agent_dev`/`agent_live` (renamed).
7. DNS port 53 / `systemd-resolved` conflict risk on Ubuntu/WSL2 (verify in Phase 3).
