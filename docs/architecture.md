# Architecture

The platform is a multi-tier, multi-tenant-ready SaaS deployment substrate. Desired
state lives in Git; deployments reconcile current → desired. See `docs/target-state.md`
for the design of record and `docs/current-state.md` for the baseline.

## Layers (strict layering — each crosses exactly ONE boundary)

```
Applications → their Environment → controlled Platform services → Infrastructure (Nginx / CI / Registry)
```

| Layer | Compose | Networks | Responsibility |
|---|---|---|---|
| Infrastructure | `infrastructure/compose.yml` | infra + platform | client entry (nginx), DNS, Git (Gitea), CI (TeamCity), private registry |
| Platform | `platform/compose.yml` | platform (+ bridges dev/live) | shared state: Postgres, Redis, Qdrant, RabbitMQ, Portkey (AI Gateway), OTEL, Langfuse, OpenObserve, and the two access gateways |
| Dev | `environments/dev/compose.yml` | dev | dev app/worker containers (reached only via dev-platform-gateway) |
| Live | `environments/live/compose.yml` | live | live app/worker containers (reached only via live-platform-gateway) |

## Networks & isolation

Four networks, each with a single owner (see `docs/networking.md`):

- `infrastructure-network` — control plane only.
- `platform-network` — shared platform services + the two gateways.
- `dev-network` — dev apps only.
- `live-network` — live apps only.

**Crossing boundaries**
- `dev-platform-gateway` attaches to `[dev-network, platform-network]` — the ONLY bridge dev↔platform.
- `live-platform-gateway` attaches to `[live-network, platform-network]` — the ONLY bridge live↔platform.
- `nginx-proxy` attaches to `[infrastructure-network, platform-network]` — the ONLY infra↔platform bridge;
  it proxies client traffic to the gateways and to control-plane UIs. It never attaches to dev/live.

Apps attach ONLY to their env network → cannot route to the other env or to platform/infra directly.
Each env reaches platform services ONLY via its own gateway, which has no route to the other env.
DB-level isolation: `agent_dev_user` owns ONLY `agent_dev`; `agent_live_user` owns ONLY `agent_live`.

## Request path

```
client
  → dnsmasq (*.local.test → host)
  → nginx-proxy :443 (infra+platform)         [TLS termination, Host-based]
  → <env>-platform-gateway :80 (platform+env) [Host-based ingress OR TCP stream]
  → app container (env network)
```

App → platform calls go the other way: `app → <env>-platform-gateway:<port> → platform service`.

## Images & promotion

Immutable `registry.local.test/aiassistant/<svc>:<git-sha>`. Dev and Live deploy the **same** tag.
Rollback = redeploy a prior tag. Never rebuild on promotion (`cicd/scripts/validate-promotion.sh`
rejects `latest` / `build:` for promoted services).

## Data flow

- **Postgres**: shared instance, per-env DBs (`agent_dev`/`agent_live` + `langgraph_*`) + platform DBs
  (langfuse, teamcity, …). Goose migrations applied per env (`migrate-dev`/`migrate-live`).
- **Redis / Qdrant / RabbitMQ**: shared, reached via gateway; tenant-readiness uses key/collection
  prefixes (config only).
- **Portkey (AI Gateway)**: ONE shared instance on platform-network; all apps route through it.
  Per-env differentiation is by `PORTKEY_MASTER_KEY`. No app holds provider logic (ADR-009).
  Apps call the OpenAI-compatible surface at `<env>-platform-gateway:4000/v1` and select a provider
  + model with the `@slug/model` form (e.g. `@groq-cloud/llama-3.3-70b-versatile`); the gateway
  resolves the provider from `platform/configs/portkey/config.json` (slugs: `groq-cloud`,
  `model-runner-local`, `openrouter-cloud`, `gemini-cloud`). Purpose-based routing/fallback
  (Phase 3) is attached per request via the `x-portkey-config` header or defaulted on the API key.
- **Observability**: OTEL collector → OpenObserve; Langfuse for LLM tracing; ClickHouse backs Langfuse.

See `docs/networking.md`, `docs/database-strategy.md`, `docs/ci-cd.md`, `docs/deployment.md`.
