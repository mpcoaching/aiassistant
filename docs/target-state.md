# Target State

> Companion to `docs/current-state.md`. Describes the architecture after the Multi-Tenant-Ready
> SaaS Deployment Platform refactor (plan `1783998200920-saas-deployment-platform-plan.md`).
> No infrastructure changes happen in this phase — this is the design of record.

---

## 1. Principles (locked)

1. **Strict env separation:** separate networks, configs, containers, volumes, credentials, targets.
   Nginx is the only sanctioned bridge for *human/client* traffic. App containers do NOT talk across
   environments.
2. **Shared Postgres, isolated DBs:** `agent_dev` / `agent_live` (and future `tenant_a_live`); users
   `agent_dev_user` / `agent_live_user`; no cross-env access (enforced by roles + GRANTs).
3. **Private registry, immutable tags:** `registry.local.test`; tag = `<git-sha>`; promote the SAME
   image; rollback = redeploy prior tag. Never rebuild on promotion.
4. **Gitea Actions + delivery CLI:** workflows in `.gitea/workflows/`; package metadata in `packages/*/package.yaml`; delivery engine in `delivery/`; immutable image promotion via registry.
5. **Nginx + dnsmasq kept** (no Traefik/Ollama); extended to `*.dev.local.test` / `*.live.local.test`
   with explicit upstreams (no dynamic regex proxy).
6. **Incremental, reversible:** 8 phases + a pre-live backup-validation gate (Phase 7.5). Legacy files
   are **archived** (not deleted) under `legacy/` for a defined stable period.

---

## 2. Network architecture (strict layering)

Each layer crosses exactly ONE boundary:

```
Applications → their Environment → controlled Platform services → Infrastructure (Nginx / CI / Registry)
```

| Network | Owner file | Members |
|---|---|---|
| `infrastructure-network` | `infrastructure/compose.yml` | nginx-proxy, dns, gitea, gitea-runner, registry |
| `platform-network` | `platform/compose.yml` | postgres, redis, qdrant, rabbitmq, litellm, otel-collector, langfuse, clickhouse, openobserve, dev-platform-gateway, live-platform-gateway (+ model-runner via host-gateway) |
| `dev-network` | `environments/dev/compose.yml` | dev app/worker containers (reached only via dev-platform-gateway) |
| `live-network` | `environments/live/compose.yml` | live app/worker containers (reached only via live-platform-gateway) |

**Crossing the boundaries**
- `dev-platform-gateway` (nginx:alpine) attaches to `[dev-network, platform-network]` — the ONLY
  bridge from dev to platform. Forwards ONLY to allowed platform backends: `postgres:5432` (stream),
  `redis:6379`, `qdrant:6333`/`6334`, `rabbitmq:5672`, `litellm:4000` (http), `otel-collector:4318`,
  `langfuse:3000`; and routes client ingress (`*.dev.local.test`) to dev app containers on `dev-network`.
  It has NO route to `live-network`.
- `live-platform-gateway` mirrors this on `[live-network, platform-network]`; no route to `dev-network`.
- `nginx-proxy` attaches to `[infrastructure-network, platform-network]` ONLY. It is the single
  Infrastructure→Platform bridge; it proxies client traffic to the per-environment gateways
  (`agent.dev.local.test → dev-platform-gateway`) and to platform/control-plane UIs. It does NOT attach
  to `dev-network`/`live-network`.
- **Path:** `client → nginx(infra+platform) → platform-gateway(platform+env) → app(env)`.
- **Docker Model Runner** is host-local; reached via `extra_hosts: model-runner.docker.internal:host-gateway`
  on apps + litellm (any network; not published to LAN).

### Why this satisfies isolation
- Apps attach ONLY to their env network → no route to the other env's apps or to platform/infra directly.
- Each env reaches platform services ONLY via its own gateway, which has no route to the other env.
- nginx crosses exactly one boundary (infra↔platform); the env↔platform boundary is crossed only by the gateway.
- DB-level: `agent_dev_user` GRANTed ONLY `agent_dev`; `agent_live_user` ONLY `agent_live`. Credentials +
  roles enforce isolation even though both gateways reach the same Postgres.
- **Fallback (only if a service cannot be proxied):** multi-home that single service onto `dev`+`live`
  and document (a) why required, (b) app-to-app traffic still impossible (distinct subnets), (c) DB
  roles/credentials block cross-env data access. Record in `docs/decisions.md`.

---

## 3. Stack → network → services

| Stack | Compose | Networks | Services |
|------|---------|----------|----------|
| Infrastructure | `infrastructure/compose.yml` | infrastructure + platform | nginx-proxy, dns, gitea, gitea-runner, registry |
| Platform | `platform/compose.yml` | platform (+ bridges dev/live) | postgres, redis, qdrant, rabbitmq, litellm, otel-collector, langfuse, clickhouse, openobserve, dev-platform-gateway, live-platform-gateway (+ model-runner host-gw) |
| Dev | `environments/dev/compose.yml` | dev | dev app/worker services (reach platform via dev-platform-gateway) |
| Live | `environments/live/compose.yml` | live | live app/worker services (reach platform via live-platform-gateway) |

### Network ownership (resolved)
The four networks are declared as real bridge networks (with explicit `name:`) in
`infrastructure/compose.yml` and referenced as `external: true` (with matching `name:`) by the
`platform`, `dev`, and `live` composes. `infrastructure` must be started first so the networks exist.
This gives each network a single owner and guarantees globally-consistent network names across all
four Compose projects (no project-prefix surprises).

---

## 4. Image / promotion model (immutable)

- Build tag = `registry.local/aiassistant/<service>:<git-sha>` (immutable manifest). Optional release
  tag `:vX.Y.Z` applied at promotion, pointing to the same manifest.
- Dev deploys `.../<service>:<git-sha>`; Live deploys the **identical** tag. Rollback = point
  `image:` at a prior `<git-sha>` and `up -d`.
- Promoted services use `image:` (registry), never `build:`. A pre-deploy validation step fails if
  `image:` contains `latest` or `build:` for a promoted service.
- Moving tags (`litellm:main-latest`, `goose-docker:latest`) are replaced with pinned references /
  digests.

---

## 5. Repository structure (target)

```
infrastructure/compose.yml
infrastructure/configs/nginx/nginx.conf
infrastructure/configs/dnsmasq/dnsmasq.conf
infrastructure/configs/registry/{htpasswd, registry.local.test.crt, registry.local.test.key}
platform/compose.yml
platform/configs/litellm/config.dev.yaml   platform/configs/litellm/config.live.yaml
platform/configs/otel/otel-collector.config.yaml
platform/db-setup/*.sql                     # db-bootstrapper + goose migrations
environments/dev/compose.yml  environments/dev/laptop.yml  environments/dev/config/*  environments/dev/.env
environments/live/compose.yml  environments/live/config/*  environments/live/.env
packages/                                       # deployable packages (each owns code, tests, Dockerfile, package.yaml)
  workflow-runner/
  control-center-ui/
  langgraph/
  opencode/
  autogen/
platform/
  configs/...
  db-setup/*.sql                                # db-bootstrapper + goose migrations
  tests/
    integration/
    e2e/
    perf/
    security/
environments/
  dev/compose.yml  dev/laptop.yml  dev/config/*  dev/.env
  live/compose.yml  live/config/*  live/.env
delivery/                                       # package-based delivery engine (discover, build, test, publish, deploy, validate)
.gitea/workflows/*.yml                          # Gitea Actions orchestration (thin)
docs/...
legacy/                                         # previous docker-compose*.yml, ai-assistant-infra/, infra/ci, migration notes
.env .env.template
```

### Move map
- `docker-compose.platform.yml` → `infrastructure/compose.yml` + `platform/compose.yml`
- `docker-compose.yml` → `environments/dev` + `environments/live`
- `docker-compose.dev.yml` → `environments/dev/laptop.yml`
- `ai-assistant-infra/configs` → `infrastructure/configs` + `platform/configs`
- `infra/ci/*` → `cicd/*`; `infra/wait_for.py` → preserved at `infra/wait_for.py` (mounted into apps)
- `agentic/src/*` + `agents/*` → `packages/*` (this phase)

---

## 6. Nginx routing (explicit upstreams — no regex)

Outer nginx (infra+platform) proxies client traffic to the per-environment gateway; the gateway
(platform+env) performs the final Host-based route to the app container. Host header is preserved.

```
upstream dev_ingress  { server dev-platform-gateway; }
upstream live_ingress { server live-platform-gateway; }

server { listen 443 ssl; server_name agent.dev.local.test;     location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name api.dev.local.test;       location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name langgraph.dev.local.test; location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name agent.live.local.test;    location / { proxy_pass http://live_ingress; } }
server { listen 443 ssl; server_name api.live.local.test;      location / { proxy_pass http://live_ingress; } }
server { listen 443 ssl; server_name langgraph.live.local.test; location / { proxy_pass http://live_ingress; } }

# dev-platform-gateway routes by incoming Host:
#   agent.dev.local.test      → dev-control-center-ui:80
#   api.dev.local.test        → dev-workflow-engine:8000
#   langgraph.dev.local.test  → dev-langgraph:8000
# (mirror for live-platform-gateway → control-center-ui / workflow-engine / langgraph)
# Control plane (nginx reaches directly on platform/infra nets):
#   gitea.local.test, registry.local.test, lf.local.test,
#   oo.local.test, otel.local.test, litellm.local.test
```

The gateway uses **nginx `stream` blocks** for TCP (Postgres 5432, Redis 6379, Qdrant 6333/6334,
RabbitMQ 5672, LiteLLM 4000, OTEL 4318, Langfuse 3000) and **`http` blocks** for client ingress.

---

## 7. Delivery capabilities

Capabilities are implemented as `delivery` CLI subcommands and orchestrated by Gitea Actions workflows.

| Capability | CLI subcommand | Purpose |
|---|---|---|
| Build | `delivery build <services>` | Build images with buildx |
| Test | `delivery test <kind>` | Run unit/integration/e2e tests |
| Publish | `delivery publish <services>` | Push images to registry |
| Deploy | `delivery deploy <env> <sha>` | Deploy to environment |
| Validate | `delivery validate <env>` | Health checks + smoke tests |
| Promote | `delivery promote <src> <dst> <sha>` | Promote release between envs |
| Rollback | `delivery rollback <env>` | Redeploy previous tag |
| Status | `delivery status [sha]` | Show release/deployment status |
| Doctor | `delivery doctor` | Verify environment prerequisites |
| Backup | `delivery backup` | Backup runtime state |
| Restore | `delivery restore <archive>` | Restore runtime state |
| Logs | `delivery logs <env>` | Stream deployment logs |

Runner uses host `/var/run/docker.sock` so builds run in host build context; host DNS applies.

---

## 8. Database strategy

Single shared Postgres; `agent_dev`/`agent_live`; `agent_dev_user`/`agent_live_user`; per-env roles +
GRANTs; no cross-env access (enforced by roles). Tenant-readiness: naming `<tenant>_<env>`; a future
`tenant_a_live` is created by a documented bootstrap SQL + user/grant + LiteLLM virtual key + Redis/Qdrant
prefixes — **configuration only, no app-code changes**. Three future options (A shared PG, B per-tenant
PG instance, C per-enterprise host) trade off isolation vs cost; design allows A→B→C by connection string
+ credentials only. Full trade-offs in `docs/database-strategy.md`.

---

## 9. Private registry

- Hostname `registry.local.test` (under `.local.test`). DNS resolves via dnsmasq wildcard (host). Pulls
  run in **host build context** (gitea-runner uses host daemon) so host DNS applies.
- TLS: cert with SAN `registry.local.test`; install the `local.test` CA into the Docker daemon trust
  store (preferred) or list `registry.local.test` under `insecure-registries` (documented trade-off).
- Auth: basic auth; credentials flow through environment `.env` files or Gitea Actions secrets.
- Rollback: `docker pull registry.local.test/aiassistant/<svc>:<prev-sha>` (immutable, already present).

---

## 10. Backup & restore (validated in Phase 7.5)

Postgres `pg_dump` per DB; registry `registry_data` volume tar; Gitea `gitea dump`; `delivery`
runtime SQLite store (`delivery/state/delivery.db`); git tag at promoted SHA + encrypted `.env`.
Rule: *a backup is not complete until its restore is tested.* Gate Live promotion on green restore tests.
Details in `docs/operations.md` + `docs/runbooks/runbook-recovery.md`.

---

## 11. Configuration change & lifecycle model

Desired state lives in Git; deployments reconcile current→desired (Compose converges; volumes persist).
Five change classes: (1) app code → rebuild only affected image; (2) infra config → `up -d <svc>`
only; (3) DB schema → goose migration + restore-tested backup first; (4) delivery CLI / workflow
change → edit workflow YAML or `delivery` subcommand, validate before apply; (5) platform service
upgrade → pin image tag, `up -d <svc>`. Full detail in `docs/deployment.md`, `docs/operations.md`,
`docs/runbooks/runbook-deployment.md`.

---

## 12. Phase order & dependency map

```
Phase 1 current-state ─┐
Phase 2 target-state  ─┤ (docs)
Phase 3 networks+control-plane  ──┐ (needs 1+2)
Phase 4 registry  ────────────────┤ (parallel w/ 3; registry on infra-net)
Phase 5 Gitea Actions + delivery ─┤ (needs infra up)
Phase 6 build & promotion ────────┤ (needs 4+5)
Phase 7 dev/live separation ──────┤ (needs 3: dev/live nets exist)
Phase 7.5 backup validation ──────┤ (gate before first Live)
Phase 8 migrate apps + archive ───┘ (last; legacy to legacy/)
```

**Dependency note:** Phase 3 (networks) must complete before Phase 7 (env separation), because
`dev-network`/`live-network` must exist before environment compose files reference them. Phase 4
(registry) can run in parallel with Phase 3 since the registry is on `infrastructure-network`.
