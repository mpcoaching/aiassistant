# Plan: Multi-Tenant-Ready SaaS Deployment Platform (Infra → Platform → Dev/Live)

> Supersedes `.kilo/plans/1783742939981-devops-infra-split-plan.md` (flat shared `ai_net`, per-env DBs only).
> This plan adds **strict network isolation via a controlled platform-access gateway**, a **private registry**,
> **TeamCity Kotlin-DSL Configuration-as-Code**, **backup/restore validation before promotion**, and
> **operator runbooks**. Preserves every "keep" (Nginx, LiteLLM, LangGraph, dnsmasq, Docker Model Runner);
> avoids every "do not use" (Traefik, Ollama).

## 0. Summary of decisions (locked)
1. **Strict env separation:** separate networks, configs, containers, volumes, credentials, targets. Nginx is
   the only sanctioned bridge for *human/client* traffic. App containers must NOT talk across environments.
2. **DB:** one shared Postgres initially; DBs `agent_dev`/`agent_live`; users `agent_dev_user`/`agent_live_user`;
   no cross-env access; future per-tenant DBs (`tenant_a_live`) possible. Migration path documented (§10).
3. **Registry:** private `registry.local.test` under `.local.test`; immutable `<git-sha>` tags; promote the SAME
   image; rollback = redeploy prior tag. Never rebuild on promotion.
4. **TeamCity CaaS:** Kotlin DSL in VCS (`cicd/teamcity/`); 10 build configs; build chains in code.
5. **Nginx/DNS:** keep Nginx (no Traefik) + dnsmasq; extend to `*.dev.local.test` / `*.live.local.test`; explicit
   upstreams (no dynamic regex proxy).
6. **Docs:** `docs/{current-state,target-state,architecture,deployment,database-strategy,ci-cd,networking,
   operations,decisions}.md` + `docs/runbooks/{runbook-startup,runbook-shutdown,runbook-deployment,
   runbook-rollback,runbook-recovery}.md`.
7. **Incremental:** 8 phases + a pre-promotion backup-validation gate (Phase 7.5). Per phase: files changed +
   test commands + expected result + rollback. Legacy files **archived** (not deleted) after a defined stable period.

---

## 1. Network architecture (layered boundaries, controlled access)

**Principle (strict layering — each layer crosses exactly ONE boundary):**
```
Applications → their Environment → controlled Platform services → Infrastructure (Nginx / CI / Registry)
```
No service is attached "everywhere". The security boundary = **network isolation + credentials + DB permissions
+ app config**.

- Shared platform services live ONLY on `platform-network`.
- Application containers attach ONLY to their environment network (`dev-network` / `live-network`); they never
  attach to `platform-network` or `infrastructure-network`.

```
infrastructure-network   nginx-proxy, dns, gitea, teamcity-server, teamcity-agent, registry
platform-network         postgres, redis, qdrant, rabbitmq, litellm, otel-collector,
                         langfuse, clickhouse, openobserve, dev-platform-gateway, live-platform-gateway
                         (+ model-runner via host-gateway)
dev-network              dev app containers            (reached only via dev-platform-gateway)
live-network             live app containers           (reached only via live-platform-gateway)
```

- **`dev-platform-gateway`** (nginx:alpine): networks `[dev-network, platform-network]` — the ONLY bridge from the
  dev environment to the platform network. Forwards ONLY to allowed platform backends: `postgres:5432` (stream),
  `redis:6379` (stream), `qdrant:6333` (stream), `rabbitmq:5672` (stream), `litellm:4000` (http),
  `otel-collector:4318` (http), `langfuse:3000` (http); and routes client ingress (`*.dev.local.test`) to the dev
  app containers on `dev-network`. It has NO route to `live-network`.
- **`live-platform-gateway`**: same on `[live-network, platform-network]`; no route to `dev-network`.
- **nginx-proxy** (client entry): networks `[infrastructure-network, platform-network]` ONLY. It is the single
  Infrastructure→Platform bridge; it proxies client traffic to the per-environment gateways (e.g.
  `agent.dev.local.test → dev-platform-gateway`) and to platform/control-plane UIs. It does NOT attach to
  `dev-network`/`live-network`, so it never directly touches application containers. Path:
  `client → nginx(infra+platform) → platform-gateway(platform+env) → app(env)`.
- **Docker Model Runner** is host-local; reached via `extra_hosts: ["model-runner.docker.internal:host-gateway"]`
  on apps + litellm (works on any network; not published to LAN).

**Why this satisfies isolation**
- Apps attach ONLY to their env network → cannot route to the other env's apps or to platform/infra directly.
- Each env reaches platform services ONLY via its own gateway, which has no route to the other env.
- nginx crosses exactly one boundary (infra↔platform); the env↔platform boundary is crossed only by the gateway.
- DB-level: `agent_dev_user` GRANTed ONLY `agent_dev`; `agent_live_user` ONLY `agent_live`. Credentials + roles
  enforce isolation even though both gateways reach the same Postgres.
- *Fallback (only if a service cannot be proxied):* multi-home that single service onto `dev`+`live` and document
  (a) why required, (b) app-to-app traffic is still impossible (distinct subnets), (c) DB roles/credentials block
  cross-env data access. Prefer the gateway; record fallback justification in `docs/decisions.md`.

---

## 2. Stack → network → services
| Stack | Compose | Networks | Services |
|---|---|---|---|
| Infrastructure | `infrastructure/compose.yml` | infrastructure + platform | nginx-proxy (infra↔platform bridge), dns, gitea, teamcity-server, teamcity-agent, registry |
| Platform | `platform/compose.yml` | platform (+ bridges dev/live) | postgres, redis, qdrant, rabbitmq, litellm, otel-collector, langfuse, clickhouse, openobserve, dev-platform-gateway, live-platform-gateway (+ model-runner host-gw) |
| Dev | `environments/dev/compose.yml` | dev | dev app/worker services (reach platform via dev-platform-gateway) |
| Live | `environments/live/compose.yml` | live | live app/worker services (reach platform via live-platform-gateway) |

---

## 3. Image / promotion model
- Build tag = `registry.local/aiassistant/<service>:<git-sha>` (immutable digest). Optional release tag `:vX.Y.Z`
  applied at promotion, pointing to the same manifest.
- Dev deploys `registry.local/aiassistant/<service>:<git-sha>`; Live deploys the **identical** tag. Rollback =
  point `image:` at a prior `<git-sha>` and `up -d`.
- Promoted services use `image:` (registry), not `build:`.

---

## 4. Repository restructure (target)
```
infrastructure/compose.yml
infrastructure/configs/nginx/nginx.conf
infrastructure/configs/dnsmasq/dnsmasq.conf
infrastructure/configs/registry/htpasswd
platform/compose.yml
platform/configs/litellm/config.yaml
platform/configs/otel/otel-collector.config.yaml
platform/db-setup/*.sql            # db-bootstrapper + goose migrations
environments/dev/compose.yml  environments/dev/config/*  environments/dev/.env
environments/live/compose.yml environments/live/config/* environments/live/.env
agents/                          # app source + Dockerfiles (control-center-ui, workflow-runner, langgraph, ...)
cicd/teamcity/settings.kts       # Kotlin DSL (CaaS)
cicd/scripts/{deploy-dev,deploy-live,rollback,integration-tests}.sh
cicd/coverage/{check-coverage.py,coverage.baseline.json}
docs/current-state.md  docs/target-state.md  docs/architecture.md  docs/deployment.md
docs/database-strategy.md  docs/ci-cd.md  docs/networking.md  docs/operations.md  docs/decisions.md
docs/runbooks/{runbook-startup,runbook-shutdown,runbook-deployment,runbook-rollback,runbook-recovery}.md
legacy/  (or archive/)            # previous docker-compose*.yml, ai-assistant-infra/, infra/ci, migration notes, rollback instructions
.env  .env.template
```
Move map (incremental): `docker-compose.platform.yml` → `infrastructure/compose.yml`+`platform/compose.yml`;
`docker-compose.yml` → `environments/dev`+`environments/live`; `docker-compose.dev.yml` → `environments/dev/laptop.yml`;
`ai-assistant-infra/configs` → `infrastructure/configs`+`platform/configs`; `infra/ci/*` → `cicd/*`; `agentic/src/*`
app services → `agents/*` (Phase 8). Legacy retained under `legacy/` until archived.

---

## 5. Phase plan (each: files changed + verify + expected + rollback)

### Phase 1 — `docs/current-state.md`  *(implement only after this doc exists)*
- Document: existing services, host ports, networks (`ai_net`,`monitoring-net`), volumes, DNS entries
  (`.local.test → host`), credential locations (`.env`, Gitea deploy key, TeamCity PG), dependencies (db-bootstrapper
  → migrate → app).
- Verify: doc matches `docker compose config` output.
- Rollback: n/a (docs).

### Phase 2 — `docs/target-state.md`  *(implement only after this doc exists)*
- Document: target architecture (§1–§3), migration plan (phase order), decisions/ADRs, network topology diagram,
  gateway design, tenant-readiness conventions.
- Verify: reviewed; no infra changes.
- Rollback: n/a.

### Phase 3 — Infrastructure stack (networks + control plane + gateways)
- `infrastructure/compose.yml`: declare **external** networks `infrastructure-network`,`platform-network`,
  `dev-network`,`live-network` (one owner file). Services: nginx-proxy (infra+platform nets), dns, gitea, teamcity-server,
  teamcity-agent.`teamcity_data`/`teamcity_logs` volumes persist server data.
- `platform/compose.yml`: shared services on `platform-network` ONLY (+ gateways added in Phase 7).
- Add `dev-platform-gateway`/`live-platform-gateway` nginx proxy services (§1) — can be defined now, used in Phase 7.
- Verify: `docker compose -f infrastructure/compose.yml up -d`; `curl -fsS http://gitea.local.test` &
  `http://teamcity.local.test` → 200; `docker network ls` shows 4 networks.
- Rollback: `down`; restore legacy `docker-compose.platform.yml`.

### Phase 4 — Private registry (`registry.local.test`)
- `registry:2` on `infrastructure-network`, volume `registry_data`, **basic auth** (`htpasswd` in
  `infrastructure/configs/registry/`), TLS cert with SAN `registry.local.test` (reuse `local.test` CA).
- Verify: `docker tag busybox registry.local.test/aiassistant/busybox:test` → `docker push` succeeds;
  unauthenticated push rejected; `docker pull` works after `docker login`.
- Rollback: stop registry; revert promoted services to local `build:` for one phase.

### Phase 5 — TeamCity Configuration-as-Code  *(see §9 for clarifications)*
- `cicd/teamcity/settings.kts` (Kotlin DSL) with 10 build configs (§7) + snapshot chains. VCS root = Gitea
  `ai/aiassistant`. Enable TeamCity "Versioned Settings" → Gitea path `cicd/teamcity`. Params externalised
  (`REGISTRY_URL`,`IMAGE_TAG`,`ENV`); secrets as TeamCity password params.
- Migrate `infra/ci/check-coverage.py`+`coverage.baseline.json` → `cicd/coverage/`; `gitea-seed.sh` → `cicd/scripts/`.
- Verify: TeamCity reloads settings from VCS (no manual BCs); dummy push triggers BC1.
- Rollback: disable Versioned Settings; restore from TeamCity history.

### Phase 6 — Image build & promotion workflow
- BCs (§7): Agent Unit Tests → Platform Unit Tests → Coverage Verification (ratchet) → Docker Image Build
  (`<git-sha>`) → Push To Registry → Deploy Development (`deploy-dev.sh`) → Integration Tests → Promotion Approval
  (manual) → Deploy Live (`deploy-live.sh`, SAME `<git-sha>`) → Rollback.
- `deploy-*.sh`/`rollback.sh` use `IMAGE_TAG`; never `build:` for promoted services.
- Verify: push → chain runs → image in `registry.local.test` → dev deploys from registry → integration green →
  approval → live deploys **same digest** (`docker inspect` digest == dev).
- Rollback: run Rollback BC with prior `IMAGE_TAG`.

### Phase 7 — Dev/Live network separation
- `environments/dev/compose.yml` & `environments/live/compose.yml`: app containers on their env net ONLY; reference
  `registry.local/aiassistant/<svc>:<tag>`; reach shared services via `dev-platform-gateway`/`live-platform-gateway`.
- nginx: explicit `*.dev.local.test` / `*.live.local.test` server blocks (§6). dnsmasq: add explicit
  `address=/.dev.local.test/<host>` + `address=/.live.local.test/<host>` (covered by `.local.test` wildcard; clarify).
- **Isolation proof:** from a dev container, `getent hosts live-*` fails / no route; write via dev → absent from
  `agent_live`; vice-versa. `curl https://agent.dev.local.test` & `https://agent.live.local.test` → 200.
- Rollback: revert to flat `docker-compose.yml` for one phase.

### Phase 7.5 — Backup & Restore Validation  *(pre-live-promotion gate — required before first Live deploy)*
- Implement backups (§11) + `docs/runbooks/runbook-recovery.md` and `docs/operations.md`.
- Tested restores (all must pass before Live promotion):
  1. **Postgres backup** (`pg_dump` of `agent_dev`/`agent_live`) → **restore test** into a scratch DB, verify row counts.
  2. **Registry backup** (volume `registry_data` snapshot/tar) → restore into temp registry, `docker pull` a tagged image.
  3. **Gitea backup** (`gitea dump`) → restore into temp Gitea, verify repo + webhook.
  4. **TeamCity backup** (`teamcity_data` volume) → restore, verify server starts + settings from VCS intact.
  5. **Configuration backup** (git tag of repo at promoted SHA; `legacy/` + `.env` encrypted copy).
- Rule: *a backup is not complete until its restore is tested.* Gate Live promotion on green restore tests.
- Rollback: n/a (validation only); if a restore fails, block promotion and fix.

### Phase 8 — Migrate applications + archive legacy
- Relocate app build contexts into `agents/`; update `environments/*/compose.yml` `build.context`. Configure
  per-env LiteLLM virtual keys / Redis DB index / Qdrant collection prefix / RabbitMQ vhost. Wire Model Runner via
  host-gateway. After stable operation for a defined period, move old `docker-compose*.yml`, `ai-assistant-infra/`,
  `infra/ci` into `legacy/` with migration notes + rollback instructions (**archived, not deleted**).
- Verify: full chain green; dev+live from registry; isolation proof holds; runbooks executable by a new engineer.
- Rollback: `git revert` relocation; legacy composes still in `legacy/`.

---

## 6. Nginx routing (explicit upstreams — no regex)
Outer nginx (on infra+platform) proxies client traffic to the per-environment gateway; the gateway (on
platform+env) performs the final host-based route to the app container. Host header is preserved.

```
upstream dev_ingress  { server dev-platform-gateway; }   # bridges platform↔dev
upstream live_ingress { server live-platform-gateway; }  # bridges platform↔live

server { listen 443 ssl; server_name agent.dev.local.test;     location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name api.dev.local.test;       location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name langgraph.dev.local.test; location / { proxy_pass http://dev_ingress; } }
server { listen 443 ssl; server_name agent.live.local.test;    location / { proxy_pass http://live_ingress; } }
server { listen 443 ssl; server_name api.live.local.test;      location / { proxy_pass http://live_ingress; } }
server { listen 443 ssl; server_name langgraph.live.local.test; location / { proxy_pass http://live_ingress; } }

# dev-platform-gateway (host-based, on dev-network) routes by incoming Host:
#   agent.dev.local.test      → dev-control-center-ui:80
#   api.dev.local.test        → dev-workflow-engine:8000
#   langgraph.dev.local.test  → dev-langgraph:8000
# (mirror for live-platform-gateway → control-center-ui / workflow-engine / langgraph)
# Control plane (unchanged, nginx reaches directly on platform/infra nets):
#   gitea.local.test, teamcity.local.test, registry.local.test, lf.local.test,
#   oo.local.test, otel.local.test, litellm.local.test
```

---

## 7. TeamCity build configurations (Kotlin DSL)
1. Agent Unit Tests — pytest (`agents/workflow-runner`) + vitest (`agents/control-center-ui`).
2. Platform Unit Tests — `platform/` service tests (extensible placeholder).
3. Coverage Verification — `cicd/coverage/check-coverage.py` ratchet vs baseline; **fail on decrease**.
4. Docker Image Build — build app images, tag `<git-sha>`.
5. Push Image To Registry — `docker push registry.local.test/aiassistant/<svc>:<git-sha>`.
6. Deploy Development — `cicd/scripts/deploy-dev.sh` (login + pull + up).
7. Integration Tests — against dev.
8. Promotion Approval — manual gate (after Phase 7.5 backup validation green).
9. Deploy Live — `deploy-live.sh` deploys SAME `<git-sha>`.
10. Rollback — `rollback.sh <prior-tag>`.

---

## 8. Quality gate
- `check-coverage.py` ratchet: parses Python `coverage.json`, vitest `coverage-summary.json`, Playwright result;
  fails if any metric < baseline; baseline raised on green `main` via bot deploy key (reused from `infra/ci/`).
- Promotion blocked unless Coverage Verification + Integration Tests + Phase 7.5 backup validation are green and
  manual approval given.

---

## 9. TeamCity architecture clarifications
- **Server persistent data:** `teamcity_data` → `/data/teamcity_server/datadir`; `teamcity_logs` →
  `/opt/teamcity/logs`. DB = shared Postgres `teamcity` DB (JDBC via `TEAMCITY_SERVER_OPTS`). Server = config +
  orchestration only.
- **Agent:** `teamcity-agent` container; executes build/test/deploy steps.
- **Docker builds:** agent uses the **host Docker daemon** (Option A) to `build`/`tag`/`push` and to run
  `docker compose` deploys — see socket decision below.
- **Registry credentials:** TeamCity password params `REGISTRY_USER`/`REGISTRY_PASSWORD`; build step runs
  `echo "$REGISTRY_PASSWORD" | docker login registry.local.test -u "$REGISTRY_USER" --password-stdin` before push;
  optionally mount a `~/.docker/config.json` secret.
- **Docker socket decision:**
  - **Option A — agent mounts host `/var/run/docker.sock`** (current, RECOMMENDED for single trusted host):
    simplest; no image cache duplication; risk = agent gains host-Docker control (near-privileged). Mitigations:
    single trusted host, agent as non-root where possible, read-only socket mount, network-restricted agent.
  - **Option B — dedicated Docker executor (dind / rootless):** stronger isolation + reproducible builds; cost =
    extra resources, registry/cache sharing complexity, LAN registry reachability from dind. Choose later if
    multi-tenant hardening demands it.
  - Decision: **Option A** now; ADR records Option B as future hardening.

---

## 10. Database strategy + future migration path
- **Current:** single shared Postgres; `agent_dev`/`agent_live`; `agent_dev_user`/`agent_live_user`; per-env roles
  + GRANTs; no cross-env access (enforced by roles). Tenant-readiness: naming `<tenant>_<env>`; future
  `tenant_a_live` created by a documented bootstrap SQL + user/grant + LiteLLM virtual key + Redis/Qdrant prefixes.
- **Future options (trade-offs in `docs/database-strategy.md`):**
  - **A — separate databases in shared Postgres** (current): lowest overhead; weakest isolation (one host/process,
    noisy-neighbor, single failure domain).
  - **B — dedicated Postgres instance per tenant**: stronger fault/resource isolation; more containers + connection
    mgmt; moderate cost.
  - **C — dedicated database host per enterprise tenant**: strongest isolation/compliance; highest cost/ops; for
    enterprise contracts.
  - Design allows moving any tenant from A→B→C without app-code changes (connection string + credentials only).

---

## 11. Private registry — networking, trust, auth, workflows
- **Hostname:** `registry.local.test` (under `.local.test`, per preference).
- **DNS resolution:** from host (Windows/WSL2) via dnsmasq `.local.test → host` (same as `gitea.local.test`). Pulls
  run in **host build context** (TeamCity agent uses host daemon) so host DNS applies. For any container runtime
  pull, attach `registry` to `dev-network`/`live-network` OR keep host-context pulls (documented).
- **TLS trust:** cert with SAN `registry.local.test`; install the `local.test` CA into the Docker daemon trust store
  (preferred) OR list `registry.local.test` under `insecure-registries` for internal-only use (documented trade-off).
- **TeamCity auth:** basic auth (`htpasswd`); agent logs in via TeamCity password params before push.
- **Dev push/pull:** `docker login registry.local.test` → `docker build -t registry.local.test/aiassistant/<svc>:<sha> .`
  → `docker push`. Pull: `docker pull registry.local.test/aiassistant/<svc>:<sha>`.
- **TeamCity push:** Build step → `docker login` → `docker build` → `docker push <sha>`.
- **Rollback:** `docker pull registry.local.test/aiassistant/<svc>:<prev-sha>` (immutable, already present) → redeploy.

---

## 12. Backup & restore procedures (validated in Phase 7.5)
- **Postgres:** `pg_dump` per DB → object/volume store; restore test into scratch DB.
- **Registry:** tar/snapshot `registry_data` volume; restore into temp registry; `docker pull`验证.
- **Gitea:** `gitea dump`; restore into temp Gitea; verify repo + webhook.
- **TeamCity:** snapshot `teamcity_data`; restore; verify server + VCS settings.
- **Config:** git tag at promoted SHA + encrypted `.env` copy + `legacy/` archive.
- All documented in `docs/operations.md` + `docs/runbooks/runbook-recovery.md`.

---

## 13. Documentation set
`docs/current-state.md`, `docs/target-state.md`, `docs/architecture.md`, `docs/deployment.md`,
`docs/database-strategy.md`, `docs/ci-cd.md`, `docs/networking.md`, `docs/operations.md`, `docs/decisions.md`,
`docs/runbooks/{runbook-startup,runbook-shutdown,runbook-deployment,runbook-rollback,runbook-recovery}.md`.
The **configuration change & lifecycle model (§17)** MUST be covered in `docs/deployment.md`, `docs/operations.md`,
and `docs/runbooks/runbook-deployment.md`.

---

## 14. Risks / caveats
- **Gateway adds a hop** for app→platform traffic (latency negligible; centralises control + auditing). Preferred
  over raw multi-homing per user direction.
- **Cross-project `depends_on`** unsupported → keep wait-loops (`/wait_for.py`) + platform-first start.
- **Model Runner host-gw** only for same-host containers; remote Fedora clients use LiteLLM→cloud.
- **Registry DNS/TLS** edge cases covered in §11; host-context pulls avoid container-self-resolution pitfall.
- TeamCity agent uses host `docker.sock` (Option A) — acceptable on single trusted host (§9).

---

## 15. Validation (end-to-end)
- `docker network ls` shows the 4 networks; `dev-platform-gateway`/`live-platform-gateway` exist.
- `curl -fsS https://agent.dev.local.test` & `https://agent.live.local.test` → 200 (explicit upstreams).
- **Isolation proof** (§7) passes; `agent_dev` write absent from `agent_live`.
- Push → Unit/Platform Tests → Coverage → Build → Push → Deploy Dev → Integration → **Phase 7.5 backups green** →
  Approval → Deploy Live, all from ONE immutable `<git-sha>`; dev & live image digests identical.
- Rollback BC redeploys prior tag; live returns to known-good.
- Drop a test → Coverage Verification fails → no promotion.

## 16. Open questions / assumptions
- **LiteLLM:** brief lists it under Platform (shared). Plan assumes ONE shared `litellm` on `platform-network`,
  reached by both envs via their gateway, with per-env virtual keys. If you prefer per-env `litellm` (current
  design), Phase 8 keeps `dev-litellm`/`litellm` on respective env nets — flag if so.
- **minio/n8n/openhands/autogen:** optional profiles; not promoted to registry initially.
- **Archive period:** "defined stable period" = e.g. 2 promotion cycles or 30 days; set in `legacy/README.md`.

## 17. Configuration change & lifecycle model
How future changes are applied **without destroying the platform**. Core invariants (the "desired state" lives in
Git; deployments reconcile current→desired):
- **Docker volumes = persistent state** — never deleted on deploy/upgrade.
- **Images = replaceable, immutable** — tagged by `<git-sha>`; never rebuilt during promotion.
- **Containers = disposable** — recreated from desired-state compose on every `up -d`.
- **Configuration = version-controlled** in Git; **the desired state lives in Git**.
- **Deployments reconcile** current state with desired state (Compose converges; volumes preserved).

Five change classes (detailed in `docs/deployment.md`, `docs/operations.md`, `docs/runbooks/runbook-deployment.md`):

1. **Application code change:** rebuild ONLY the affected service image →
   `docker build -t registry.local.test/aiassistant/<svc>:<new-sha> .` → push → promote the SAME tag through
   Dev → Integration → Approval → Live. Other services untouched.
2. **Infrastructure configuration change:** edit compose/config in Git →
   `docker compose -f infrastructure/compose.yml up -d <only-affected-service>` (Compose recreates only changed
   services; **named volumes persist**). Example: change an nginx upstream → `up -d nginx-proxy`.
3. **Database schema change:** author a goose migration in `platform/db-setup/migrations` → require a
   **restore-tested backup** (Phase 7.5) BEFORE any destructive migration → apply via the `migrate` job →
   rollback = down-migration to previous known-good. Never hand-edit prod; destructive migrations need a
   verified backup first.
4. **TeamCity Configuration-as-Code change:** edit `cicd/teamcity/settings.kts` → commit to Gitea → TeamCity
   detects the config change from VCS → **validate** (DSL compile + dry-run) before applying; a broken config is
   rejected and the previous config remains active.
5. **Platform service upgrade:** update the pinned image tag in compose (e.g. `postgres:16.x`) →
   `docker compose -f platform/compose.yml up -d <svc>` → rely on healthchecks → rollback = revert the image tag
   in Git + `up -d` to the previous image.
