# Plan: Infra Split — Platform/CI Stack + Dev/Live Environments + UI Testing

## Goal
Self-hosted DevOps/CI (TeamCity + Gitea) that is **independent** of the agentic system, plus a
clean **dev vs live** separation so the live system is fast, easy to manage, and isolated. The dev
environment is a conveniently-runnable, slower, source-mounted setup; live is promoted, prod-built,
and fully separated at the data layer. Rebuild/restart of any one tier must not take the others down.
CI builds & tests the repo (Python + TypeScript UI), enforces a **ratcheting 100% coverage gate**,
and promotes **dev → live**.

## Confirmed decisions
- CI server: **TeamCity** (server + agent). Source of truth: **self-hosted Gitea** (nginx-proxied, webhook → TeamCity).
- Coverage gate: **ratchet to 100%** (fail on regression vs stored baseline; raised on `main`).
- **Dev/Live isolation: separate app instances + per-env databases.** Dev and live each run their own
  `workflow-engine`/`langgraph`/`litellm` instances; each env gets its own Postgres database
  (`*_dev` vs `*_live`). They share only the Tier-0 substrate. Dev data can never touch live.
- **UI testing: mocked units + a thin Playwright e2e slice.** `vitest` + `@testing-library/react`
  with the API layer mocked (MSW / `vi.mock`) for fast deterministic unit coverage; a small number of
  Playwright critical-path tests for confidence. No broad e2e surface.

## Server inventory (what runs, and what it does)
All reachable from the laptop via `*.local.test` (dnsmasq → 192.168.1.238 → nginx-proxy:80).

### Tier 0 — Platform substrate (always-on, shared; owned by `docker-compose.platform.yml`)
| Server | Does |
|---|---|
| nginx-proxy | Reverse proxy for every `*.local.test` subdomain (md5-watch + reload) |
| dns (dnsmasq) | Resolves `*.local.test` → host IP |
| postgres | Shared RDBMS. One database per env/role (`aiassistant_dev`, `aiassistant_live`, `langgraph_*`, `litellm_*`, `teamcity`, n8n, langfuse, openobserve, openhands) |
| db-bootstrapper | Creates DBs/users/grants from `db-setup/*.sql` via envsubst |
| migrate (goose) | Applies migrations to `aiassistant_*` DBs |
| rabbitmq | Shared event bus (ai_net) |
| qdrant | Shared vector store |
| redis / redis-agents | Shared caches |
| langfuse + clickhouse + redis(monitoring) | LLM observability |
| otel-collector + openobserve | Telemetry pipelines |
| teamcity-server | CI server (UI/build configs), backed by shared Postgres `teamcity` DB |
| teamcity-agent | CI build agent; uses host `/var/run/docker.sock` to run sibling build/promotion containers |
| gitea | Git source of truth; holds repo + `infra/ci/coverage.baseline.json` |

### Tier 1 — Live (promoted, prod builds, separated) → `control-center.local.test`
| Server | Does |
|---|---|
| control-center-ui (live) | Multi-stage `nginx:alpine` serving the prod `dist` SPA → fast static, no runtime |
| workflow-engine (live) | Prod image, `DATABASE_URL=…aiassistant_live` |
| langgraph (live) | Prod image, `DATABASE_URI=…langgraph_live` |
| litellm (live) | Prod image, `DATABASE_URL=…litellm_live` |
| (optional) openhands/aider/autogen/n8n | Live copies as needed, on `*_live` DBs |

### Tier 2 — Dev (convenience, slow OK, source-mounted) → `dev.local.test`
| Server | Does |
|---|---|
| dev-controller | **The single dev UI server**: `vite` HMR dev server, source-mounted, port 8443. Slow is fine. (Wires up the existing nginx stub `dev.local.test → dev-controller:8443`.) |
| dev-workflow-engine | Source-mounted dev copy, `DATABASE_URL=…aiassistant_dev` |
| dev-langgraph | Source-mounted dev copy, `DATABASE_URI=…langgraph_dev` |
| dev-litellm | Source-mounted dev copy, `DATABASE_URL=…litellm_dev` |

Both tiers run simultaneously on the same host; separation is at the **database** layer, not the network.

## Target topology — two compose projects, one shared external network
```
LAPTOP  ── *.local.test (dnsmasq → 192.168.1.238) ──▶ nginx-proxy (platform, :80)
                                                            ├─ teamcity.local.test   → teamcity-server:8111
                                                            ├─ gitea.local.test      → gitea:3000
                                                            ├─ control-center.local.test → control-center-ui:80   (LIVE)
                                                            └─ dev.local.test        → dev-controller:8443        (DEV)
```
- **Platform stack** (`docker-compose.platform.yml`): owns `ai_net` + `monitoring-net` (defined here,
  not external). Contains nginx-proxy, dns, postgres, db-bootstrapper, migrate, rabbitmq, qdrant,
  redis, redis-agents, langfuse, clickhouse, otel-collector, openobserve, gitea, teamcity-server,
  teamcity-agent.
- **Agentic stack** (`docker-compose.yml`, slimmed): app services that change during dev. Declares
  `ai_net` + `monitoring-net` as `external: true`. Contains the **dev tier** (`dev-controller`,
  `dev-workflow-engine`, `dev-langgraph`, `dev-litellm`) and the **live tier** (`control-center-ui`,
  `workflow-engine`, `langgraph`, `litellm`), plus optional `openhands`/`aider`/`autogen`/`n8n`/`workspace`.
  db-bootstrapper + migrate live in PLATFORM.

### Dependency mapping (cross-project `depends_on` is NOT supported by Compose)
Platform-first start; agentic services replace cross-project `depends_on` with startup wait-loops:

| Service (agentic) | Drops `depends_on` on | Replaced by wait-loop |
|---|---|---|
| dev-langgraph / langgraph | postgres | `pg_isready -h postgres` |
| dev-litellm / litellm | migrate, redis-agents | postgres-ready + `redis-cli -h redis-agents ping` |
| dev-workflow-engine / workflow-engine | migrate, rabbitmq (+ langgraph) | postgres-ready + `rabbitmqctl await_startup` |

## Prerequisites / gaps (do first)
1. **Python test deps**: `agentic/src/workflow-runner/requirements.txt` lacks pytest → add
   `requirements-dev.txt` (pytest, pytest-cov). 96 passing tests already exist.
2. **TypeScript UI harness**: `package.json` has no test framework (only `dev`/`build`/`preview`).
   Bootstrap: add `vitest` + `@vitest/coverage-v8` + `@testing-library/react` + `@testing-library/jest-dom`
   + `msw` as devDependencies; add `"test": "vitest run"` and `"test:e2e": "playwright test"` scripts;
   add `vitest.config.ts` (jsdom env, json coverage); add `playwright.config.ts` (baseURL
   `http://dev.local.test`); write ≥1 smoke test (renders `<App/>`) + ≥1 mocked-API test.
3. **Playwright**: CI step runs `npx playwright install --with-deps chromium` (needs the node:20 image
   to allow browser deps, or a `@playwright/test` image).
4. **Per-env DBs**: extend db-setup (below) and `.env` with `*_DEV` / `*_LIVE` database names; reuse
   existing roles (same role owns both dev and live DB for an app).

## Changes — Platform stack (`docker-compose.platform.yml`)
- Move from current `docker-compose.yml`: nginx-proxy, dns, postgres, db-bootstrapper, migrate,
  rabbitmq, qdrant, redis, redis-agents, langfuse, clickhouse, otel-collector, openobserve. Define
  `ai_net`+`monitoring-net` here. Keep config/volumes.
- **Gitea** (new): `gitea/gitea:latest`, :3000, `gitea_data`, SQLite built-in. Seed org/user `ai` +
  repo `aiassistant`; deploy key + webhook → TeamCity.
- **TeamCity server** (new): `jetbrains/teamcity-server:latest`, :8111, `teamcity_data`/`teamcity_logs`,
  backed by shared Postgres `teamcity` DB via `config/database.properties` (HSQLDB fallback if undesired).
- **TeamCity agent** (new): `jetbrains/teamcity-agent:latest` (+ `docker` CLI/`compose` plugin),
  `SERVER_URL=http://teamcity-server:8111`, mounts host `/var/run/docker.sock`.

### db-setup additions
- `001_create_databases.sql`: add `('${AIASSIST_DEV_DB_NAME}')`, `('${AIASSIST_LIVE_DB_NAME}')`,
  `('${LANGGRAPH_DEV_DB_NAME}')`, `('${LANGGRAPH_LIVE_DB_NAME}')`, `('${LITELLM_DEV_DB_NAME}')`,
  `('${LITELLM_LIVE_DB_NAME}')`, `('${TEAMCITY_DB_NAME}')` to the VALUES list.
- `002_create_users.sql`: add `('${TEAMCITY_DB_USER}', '${TEAMCITY_DB_PASSWORD}')`. (Per-env DBs reuse
  the existing `AIASSIST`/`LANGGRAPH`/`LITELLM` roles — no new roles needed.)
- `003_apply_permissions.sql`: add the new DB/role pairs, including the dev/live variants.
- `.env` / `.env.template`: add `*_DEV_DB_NAME`, `*_LIVE_DB_NAME`, `TEAMCITY_DB_*`.

## Changes — Agentic stack (`docker-compose.yml`, slimmed)
- Remove: nginx-proxy, dns, postgres, db-bootstrapper, migrate, rabbitmq, qdrant, redis, redis-agents,
  langfuse, clickhouse, otel-collector, openobserve. Mark `ai_net`/`monitoring-net` external.
- Apply wait-loop conversions (table above) — drop cross-project `depends_on`.
- **Rename the dev UI service** `control-center-ui-dev` → `dev-controller`: `node:20-alpine`, source
  mounted, `command: sh -c "npm install && npm run dev -- --port 8443 --host 0.0.0.0"`, expose `8443`.
- **Add dev-tier app instances**: `dev-workflow-engine`, `dev-langgraph`, `dev-litellm` — same builds as
  live but source-mounted (`:cached`) and pointed at `*_DEV` DBs. Wait-loops instead of `depends_on`.
- **Live-tier instances** stay as `control-center-ui` (Dockerfile `target: live`), `workflow-engine`,
  `langgraph`, `litellm`; point at `*_LIVE` DBs.
- Keep `openhands`/`aider`/`autogen`/`n8n`/`workspace` as optional profiles.

## nginx additions (`ai-assistant-infra/configs/nginx/nginx.conf`)
Uncomment/wire the dev block and add CI blocks:
```
server { listen 80; server_name dev.local.test;       location / { proxy_pass http://dev-controller:8443; } }
server { listen 80; server_name gitea.local.test;     location / { proxy_pass http://gitea:3000; } }
server { listen 80; server_name teamcity.local.test;  location / { proxy_pass http://teamcity-server:8111; } }
```
(keep `control-center.local.test → control-center-ui:80`). 443/TLS out of scope.

## Gitea setup
Org/user `ai`, repo `aiassistant` (mirror current tree); read/write deploy key; webhook → TeamCity.
Repo holds `infra/ci/coverage.baseline.json = { "python": 0.0, "ts": 0.0, "e2e": 0.0 }` (ratcheted up).

## UI testing strategy
- **Units (mocked)**: `vitest` + `@testing-library/react`; network mocked via `msw` (or `vi.mock` of the
  API client). Tests render components/hooks in `jsdom`, assert behaviour, no browser. Feeds TS coverage.
- **e2e slice (Playwright)**: a small, curated set of critical-path specs (e.g. app loads, submits a
  workflow) run against the **dev** environment (`http://dev.local.test`) in CI. Not a broad suite.
- Both run in BC1; the ratchet covers `ts` (units) and `e2e` (path count) baselines.

## TeamCity build configuration (3 build configs)
- **BC1 — Test & Build** (trigger: Gitea push/PR):
  - Step 1 (Python): `docker run --rm -v $PWD:/src -w /src/agentic/src/workflow-runner python:3.12-slim bash -c "pip install -r requirements.txt -r requirements-dev.txt && pytest --cov=. --cov-report=json"`
  - Step 2 (TS units): `docker run --rm -v $PWD:/src -w /src/agentic/src/control-center-ui node:20 bash -c "npm ci && npx vitest run --coverage --reporter=json"`
  - Step 3 (Playwright e2e): bring up dev-tier (`docker compose up -d dev-controller dev-workflow-engine dev-langgraph dev-litellm`), `npm ci && npx playwright install --with-deps chromium && npx playwright test`, then tear down.
  - Step 4 (ratchet): `python infra/ci/check-coverage.py …` → **fail on regression**.
  - Step 5 (main only): commit raised baseline back to Gitea via bot deploy key.
- **BC2 — Promote to Dev** (snapshot dep on BC1; auto on `main`): `docker compose up -d --build dev-controller dev-workflow-engine dev-langgraph dev-litellm` (redeploy dev tier from latest source).
- **BC3 — Promote to Live** (snapshot dep on BC1; **manual approval**): `docker compose up -d --build control-center-ui workflow-engine langgraph litellm` (deploy prod-built live tier).

## Coverage ratchet mechanism
`infra/ci/check-coverage.py` (new): parse Python `coverage.json` (`totals.percent_covered`), vitest
`coverage-summary.json` (`total.lines.pct`), and Playwright (`*.xml`/json spec count); fail if
`current < baseline` per key. On green `main`, Step 5 writes the new (raised) baseline.

## Startup / operations order
1. `docker compose -f docker-compose.platform.yml up -d` (creates networks, db-bootstrapper+migrate,
   nginx/dns/TeamCity/Gitea; creates `*_dev`/`*_live`/teamcity DBs).
2. `docker compose up -d` (agentic stack joins external networks; dev + live tiers start on their DBs).
3. Laptop: `teamcity.local.test`, `gitea.local.test`, `control-center.local.test` (live),
   `dev.local.test` (dev).
4. Push to Gitea → BC1 → on success BC2 promotes dev (auto); manual BC3 promotes live.

## Risks / caveats
- Cross-project `depends_on` unsupported → wait-loops + platform-first start mitigate.
- TeamCity agent uses host docker.sock (sibling containers), not full dind — acceptable on one host.
- Dev + live app instances run simultaneously (~8 extra containers); fine on a dev host.
- Live promotion gated by ratchet; until TS/e2e coverage exists, live stays on last promoted build (by design).
- Playwright needs browser deps in the CI image — add `@playwright/test` + `playwright install`.
- Retire `.github/workflows/control-center-ui.yml` (superseded by TeamCity); GitHub optional mirror.

## Validation
- `docker network ls` shows `ai_net`/`monitoring-net` owned by platform project.
- `curl -fsS http://teamcity.local.test` and `http://gitea.local.test` resolve from laptop.
- `curl -fsS http://control-center.local.test` (live prod SPA) and `http://dev.local.test` (dev HMR) both work.
- Restart/rebuild agentic stack → nginx/dns/postgres/TeamCity/Gitea stay up; restart platform → agentic stays on external networks (reconnects).
- Write a row into dev DB via dev endpoint; confirm it is **absent** from the `*_live` DB (isolation proof).
- Push dummy commit → BC1 (py+ts units+playwright) runs; ratchet passes; BC2 promotes dev; manual BC3 promotes live.
- Deliberately drop a UI unit test → BC1 fails (ratchet regression) → no promotion.

## Open questions / out of scope
- TLS/443, multi-host/HA, secrets vault (use `.env`), dedicated rollback UI (TeamCity history + prior compose state suffice).
- Whether live should also get its own `openhands`/`aider`/`autogen` copies (default: optional, off).
