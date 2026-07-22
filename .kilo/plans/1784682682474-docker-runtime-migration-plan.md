# Docker Runtime Migration Plan — Docker Desktop → WSL2 Ubuntu Native Engine

## 1. Current State (baseline)

The repository has already undergone a major refactor (the "SaaS Deployment Platform" plan, 1783998200920). Current compose structure:

| Compose project | File | Starts |
|---|---|---|
| Infrastructure | `infrastructure/compose.yml` | 1st (creates all networks) |
| Platform | `platform/compose.yml` | 2nd |
| Dev | `environments/dev/compose.yml` | 3rd |
| Live | `environments/live/compose.yml` | 3rd |

Networks: `infrastructure-network`, `platform-network`, `dev-network`, `live-network`, `ai_net` (external).

Local dev uses `environments/dev/laptop.yml` (merged with `environments/dev/compose.yml`), which provides:
- A `docker-dind` sidecar (`docker:dind`, privileged)
- A VS Code `workspace` container pointing `DOCKER_HOST=tcp://docker-dind:2375`

---

## 2. Gap Analysis

### 2.1 Docker Desktop Feature Coupling

| Dependency | Location | Severity |
|---|---|---|
| `extra_hosts: model-runner.docker.internal:host-gateway` | `platform/compose.yml:146`, `environments/dev/compose.yml:42,82`, `environments/live/compose.yml:38,70` | High — Docker Model Runner hostname |
| `base_url: http://model-runner.docker.internal:12434/...` | `platform/configs/portkey/config.json:58` | High — Portkey routes to Docker Model Runner |
| `DOCKER_HOST=tcp://docker-dind:2375` | `.devcontainer/devcontainer.json:7`, `environments/dev/laptop.yml:21` | High — Local dev depends on dind |
| `docker-dind` service definition | `docker-compose.dev.yml:27-45`, `legacy/docker-compose.dev.yml:27-45`, `environments/dev/laptop.yml:30-48` | High — Complete local dev overlay |

### 2.2 Windows-Specific / Host-Dependent Artifacts

| Dependency | Location | Severity |
|---|---|---|
| AIASSIST_PATH Windows path leak | `.env:14` | High — breaks inside WSL2 containers |
| Volume mount `:z` / `:cached,z` | `docker-compose.yml:52,123,159`, `legacy/docker-compose.yml:52,159` | Medium — Linux SELinux labels; unnecessary on WSL2 |
| Legacy duplicate compose files at repo root | `docker-compose.yml`, `docker-compose.platform.yml`, `docker-compose.dev.yml` | Medium — Mirror of canonical files; risk of dual runbooks |

### 2.3 What the Refactor Fixed (do not regress these)

- Environment separation via four networks with single owners
- Explicit `name:` on networks (no project-prefix surprises)
- Platform services moved out of `ai_net` into `platform-network`
- Per-environment gateways (`dev-platform-gateway`, `live-platform-gateway`)
- Immutable image promotion model and registry (`registry.local.test`)
- Windows path `AIASSIST_PATH` flagged as removed in ADR-008 but **still present in `.env`**
- LiteLLM replaced by Portkey (ADR-009) — legacy `litellm` service removed

---

## 3. Migration Principles (from ADR)

1. **Docker is an implementation detail** — apps depend on container networking, HTTP APIs, env config, service discovery.
2. **AI runtime is separate from application runtime** — Docker Model Runner is not part of the platform architecture. Accessed through Portkey.
3. **Local infrastructure must not affect host networking** — failure of CoreDNS/nginx/Portkey/containers must not break general Internet or host operation.
4. **Infrastructure remains configuration driven** — compose files + config + env files.
5. **Primary clients are Linux endpoints** — WSL2 Ubuntu and Fedora workstation are first-class; Windows host access is secondary. The platform must not depend on Windows-specific networking behaviour.

---

## 4. Target Architecture (WSL2 Ubuntu native)

```
Windows host
  └── WSL2 Ubuntu
        └── Docker Engine (dockerd, native)
              ├── infrastructure-network
              │     ├── nginx-proxy
              │     └── CoreDNS (sole .local.test authority)
              ├── platform-network
              │     ├── postgres, redis, qdrant, rabbitmq
              │     ├── portkey, langfuse, clickhouse, openobserve, otel-collector
              │     └── dev-platform-gateway / live-platform-gateway
              ├── dev-network
              │     └── dev app/worker containers (reach platform via dev-platform-gateway)
              └── live-network
                    └── live app/worker containers (reach platform via live-platform-gateway)
```

Key change: **VS Code Remote WSL** connects directly to the WSL2 Docker Engine. No dind sidecar.

### DNS architecture

CoreDNS is the **only** `.local.test` DNS authority.

```
Clients → CoreDNS → nginx-proxy → services
```

CoreDNS is attached only to `infrastructure-network` (simplest control-plane design). It is **not** attached to `platform-network`, `dev-network`, or `live-network`.

### Local dev workflow change

| Before | After |
|---|---|
| VS Code devcontainer → dind sandbox | VS Code Remote WSL → host Docker Engine (WSL2) |
| `DOCKER_HOST=tcp://docker-dind:2375` | DOCKER_HOST unset (docker CLI talks to `/var/run/docker.sock` mounted by Remote WSL) |
| `docker-dind` service in `laptop.yml` | No dind service |
| `docker compose -f ... -f laptop.yml up` | Direct host `docker compose -f environments/dev/compose.yml up` |

### Optional operations tooling

`management/compose.yml` is **optional** and **not required** for platform startup or dependencies.

Contains administrative inspection tools only:
- **Portainer** — container management UI
- **Dockge** — compose stack manager

Attaches to `infrastructure-network` and `platform-network` only. Profiles or separate activation; never started by production or dev workflows.

---

## 5. Implementation Plan

### Phase 0 — Discovery (read-only)

No changes. Confirm current environment before touching anything.

1. **Record Docker context and daemon location.**
   - `docker context ls`
   - `docker info --format '{{.DockerRootDir}}'`
   - Confirm current Docker host (Docker Desktop vs native).

2. **Check for existing native Docker Engine inside WSL2 (if any).**
   - `wsl -l -v` (from Windows) or `wsl --status`
   - Inside WSL2: `which dockerd`, `systemctl status docker`, `ps aux | grep dockerd`

3. **Check WSL systemd status.**
   - `/etc/systemd/system` exists and enabled
   - `systemctl is-system-running`

4. **Inventory current Docker sockets.**
   - `/var/run/docker.sock` (host)
   - Named sockets if any
   - Permissions and ownership

5. **Inventory current Docker volumes.**
   - `docker volume ls`
   - Record mount points and sizes

6. **Inventory current Docker networks.**
   - `docker network ls`
   - Record drivers and scopes

7. **Document current compose configuration.**
   - Export running config: `docker compose -f infrastructure/compose.yml config`, `docker compose -f platform/compose.yml config`, `docker compose -f environments/dev/compose.yml config`, `docker compose -f environments/live/compose.yml config`
   - Capture env files (`.env` content, without secrets where possible)

8. **Document existing images.**
   - `docker images`

**Output:** Discovery report. No changes made.

---

### Phase 1 — Backup & Rollback Preparation

Before touching the runtime, produce recoverable artifacts.

9. **Backup current state.**
   - Docker volumes: `docker run --rm -v <volume>:/data -v $(pwd)/backups:/backup alpine tar czf /backup/<volume>.tar.gz /data` for each named volume.
   - Key volumes: `postgres_db`, `gitea_data`, `registry_data`, `qdrant_data`, `langfuse_data`, `clickhouse_data`, `openobserve_storage`, `redis_agents_data`, `langfuse_redis_data`, `rabbitmq_data`, `minio_data`, `n8n_data`, `langgraph_config`, `dind_data`.
   - Database dumps:
     - PostgreSQL: `docker compose -f infrastructure/compose.yml exec postgres pg_dump -Fc -U postgres > backups/postgres_all.dump`
     - (If enabled) n8n: `docker compose exec n8n n8n export:workflow --all --output=/backups/n8n-workflows.tar.gz`
   - CoreDNS config: `cp infrastructure/configs/coredns/Corefile backups/Corefile`
   - Environment config: sanitised `.env` backup (redact secrets) and full encrypted `.env` backup per runbooks.
   - Current compose files: git commit or tar of working tree.

10. **Validate backup/restore procedures.**
    - Restore each volume tar to a scratch container and verify file counts.
    - Restore PostgreSQL dump into a scratch DB and verify row counts / schema.
    - Restore Gitea dump into a temp Gitea container and verify repo + webhook presence.
    - Restore Qdrant data into a temp Qdrant and verify collection snapshots.
    - Restore registry data into a temp registry and verify manifest list for known images.
    - (If enabled) Restore n8n workflow export and verify load.

11. **⚠️ Critical constraint: Docker Desktop volumes are not automatically available to native WSL2 Docker Engine.**
    - Named volumes created under Docker Desktop live in a Docker Desktop managed storage area.
    - These volumes cannot be mounted by a separate native Docker Engine instance.
    - If persistence of existing data is required, back up volumes **before** stopping Docker Desktop and **before** starting the native engine.
    - Restore from backups after native engine is running.

---

### Phase 0 — Preparation (no runtime changes)

12. **Audit and freeze Docker Model Runner references.**
    - Replace all `model-runner.docker.internal` with a provider-agnostic configuration.
    - Introduce a single `AI_PROVIDER_BASE_URL` env var (default: empty / unset).
    - In `platform/configs/portkey/config.json`, replace the hard-coded `model-runner.docker.internal:12434` with a value resolved from the Portkey `AI_PROVIDER_BASE_URL` environment variable.
    - Rationale: model runtime is swappable (Docker Model Runner, Ollama, vLLM, cloud). Remove Docker Desktop coupling. Avoid variable names that preserve Docker Desktop assumptions (`MODEL_RUNNER_HOST` implies Docker Model Runner is the default).

13. **Remove the Windows path leak from `.env`.**
    - Delete line 14 (`AIASSIST_PATH=C:/Users/marti_ve1yzb6/Documents/...`).
    - Add a `.env.template` entry showing the variable is deprecated / removed.

14. **Clean volume mount options.**
    - Strip `:z` and `:cached,z` suffixes from `docker-compose.yml` (root), `legacy/docker-compose.yml`, and `environments/dev/laptop.yml`.
    - On WSL2 / Ubuntu Docker Engine these are unnecessary; clean them for Linux-native hygiene.

---

### Phase 1 — WSL2 Ubuntu Docker Engine Setup (pilot)

15. **Install Docker Engine in WSL2 Ubuntu.**
    - Follow Docker's official Ubuntu install guide (`apt install docker-ce docker-ce-cli containerd.io`).
    - Configure daemon:
      - Start dockerd automatically on WSL2 boot (systemd or `/etc/init.d` wrapper).
      - Ensure `/var/run/docker.sock` has consistent permissions for the dev user.
    - Validate:
      - `docker info` shows Linux kernel, cgroup driver.
      - `docker compose version` works.
      - `docker compose up` can start a trivial `hello-world` stack.
      - Volumes persist across `docker compose down` / `up`.
      - Container lifecycle (restart policies, depends_on) works predictably.

16. **Validate networking on the native engine.**
    - Create the four networks with explicit names.
    - Confirm `bridge` driver networking behaves identically to the Docker Desktop target.
    - Confirm CoreDNS on `infrastructure-network` resolves `.local.test` hostnames correctly from WSL2 Ubuntu and Fedora clients.
    - Verify `nginx-proxy` publishes `:80/:443` reachable from Fedora (`http://<wsl2-ip>`) and Windows host (`http://localhost`).

17. **Simplify CoreDNS network attachment.**
    - CoreDNS attaches only to `infrastructure-network`.
    - No attachment to `platform-network`, `dev-network`, or `live-network`.
    - If CoreDNS does not already need `platform-network` for any reason in the current `infrastructure/compose.yml`, remove it.
    - Rationale: simplest control-plane design; CoreDNS is the single `.local.test` authority and does not need visibility into app-layer networks.

18. **Validate `host-gateway` compatibility (or remove dependency).**
    - In `/etc/docker/daemon.json`, check whether `"experimental": true` is needed for `--add-host=host.docker.internal:host-gateway` on Linux Docker Engine (Docker 20.10+ supports it without experimental, but verify).
    - If not supported, remove `extra_hosts: model-runner.docker.internal:host-gateway` from all compose files and rely entirely on `AI_PROVIDER_BASE_URL` for model routing.
    - Preferred resolution: **remove the dependency**; apps should never assume Docker Model Runner is the default model runtime.

---

### Phase 2 — Incremental Service Migration

19. **Pilot: infrastructure stack (nginx, CoreDNS, gitea, registry).**
    - Start `infrastructure/compose.yml` on the native engine.
    - Verify from WSL2 Ubuntu and Fedora workstation:
      - CoreDNS resolves `gitea.local.test`, `registry.local.test`, etc.
      - `docker pull registry.local.test/...` trusts the local CA.
    - Verify from Windows host (secondary):
      - `http://gitea.local.test` resolves.
      - `http://registry.local.test` reachable.

20. **Pilot: platform stack (postgres, redis, qdrant, rabbitmq, portkey, langfuse, clickhouse, openobserve, otel-collector).**
    - Start `platform/compose.yml`.
    - Run `db-bootstrapper` and migrations.
    - Validate healthchecks, volumes, and cross-network traffic through gateways.
    - Confirm Portkey uses `AI_PROVIDER_BASE_URL` (no Docker Desktop assumptions).

21. **Pilot: dev environment.**
    - Start `environments/dev/compose.yml`.
    - Update local dev workflow: developers use VS Code Remote WSL and talk directly to the WSL2 Docker Engine.
    - Remove `docker-dind` concept; no `/var/run/docker.sock` mount to an inner container.
    - Validate single-service sandbox works directly on host daemon.

22. **Pilot: live environment.**
    - Start `environments/live/compose.yml`.
    - Validate isolation: dev traffic cannot reach live containers or platform services except through approved gateways.

23. **Deploy optional management tools (if desired).**
    - `docker compose -f management/compose.yml up -d`
    - Validate Portainer / Dockge can inspect the platform stacks.
    - Confirm management stack has no platform dependencies (it is purely additive).

24. **Later migration (post-pilot validation):**
    - Databases (ensure volume data restored successfully from backups).
    - Gitea (already in infrastructure; validate data persists).
    - n8n (optional; currently disabled).
    - Persistent application data volumes.

---

### Phase 3 — Validation & Stabilisation

25. **Validate from primary clients.**
    - **WSL2 Ubuntu:** all `.local.test` services resolve; platform starts/stops cleanly.
    - **Fedora workstation:** core DNS routing works via split-DNS or hosts file; HTTPS to `registry.local.test` works with local CA.
    - **Windows host (secondary):** basic reachability via `http://localhost` through nginx-proxy; not a hard requirement.

26. **Validate Portkey AI routing.**
    - Portkey starts without `AI_PROVIDER_BASE_URL` (no default provider).
    - Portkey resolves providers from `AI_PROVIDER_BASE_URL` when set.
    - Confirm Docker Model Runner, Ollama, vLLM, and cloud providers are all reachable through Portkey when configured.

27. **Validate rollback exists.**
    - If native engine fails, Docker Desktop can be restarted with restored volume data to resume.
    - Document exact rollback commands and expected downtime.

28. **Normal development workflow test.**
    - Developer opens repo via VS Code Remote WSL.
    - `docker compose -f environments/dev/compose.yml up -d` works.
    - Single-service rebuild + redeploy works.
    - No dind sidecar required.

---

### Phase 4 — Cleanup (only after Phase 2–3 success)

**Do not perform cleanup until migration succeeds, backup/restore is validated, and normal development workflow has been tested.**

29. **Remove Docker Desktop assumptions from developer docs.**
    - Update `docs/dev-environment.md`: describe VS Code Remote WSL + host Docker Engine workflow; replace dnsmasq references with CoreDNS.
    - Update `docs/networking.md`: replace dnsmasq references with CoreDNS; remove Docker Model Runner hard-coupling references; document model runtime as an external provider.
    - Update `docs/current-state.md` to reflect the new runtime baseline.
    - Update `docs/target-state.md` to remove Docker Desktop from the design of record.

30. **Update runbooks.**
    - `docs/runbook-startup.md`: WSL2-specific steps (start WSL, ensure dockerd running, compose order).
    - `docs/runbook-shutdown.md`: WSL2-specific graceful shutdown.

31. **Update ADRs.**
    - Add new ADR: WSL2 native Docker Engine as the runtime boundary.
    - Update ADR-002: record single trusted native Docker Engine on WSL2 Ubuntu; dind sidecar retired.

32. **Remove legacy files.**
    - Delete root `docker-compose.yml`, `docker-compose.platform.yml`, `docker-compose.dev.yml` (mirrors of canonical files).
    - Delete `legacy/` directory files that are superseded by the refactored composes.
    - Update `docs/decisions.md` ADR-001 to reflect the new archive timeline.

---

## 6. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| WSL2 networking differs from Docker Desktop networking | Discovery Phase 0 captures current state; Pilot Phase 1 validates bridge networking from WSL2 and Fedora before migrating services. |
| CoreDNS port 53 / `systemd-resolved` conflict on Ubuntu/WSL2 | Verify CoreDNS startup in Phase 1. If `systemd-resolved` binds port 53, stop/disable it or rebind CoreDNS. |
| `host-gateway` not available on Linux Docker Engine | Remove `extra_hosts` dependency in Phase 1; rely on `AI_PROVIDER_BASE_URL` for model routing. |
| Developer workflow disruption | Remote WSL + host Docker is simpler than dind; update docs and provide a 1-page onboarding checklist. |
| Data loss during engine swap | Named Docker volumes are engine-agnostic, but **Docker Desktop volumes are not portable** to a separate native engine. Back up all volumes in Phase 1 before stopping Docker Desktop. |
| `dind` sidecar was providing isolation | Host daemon in WSL2 is sufficient isolation for a single-operator dev box; adoption is single-trusted-host (same as ADR-002). |
| Windows host becomes a hidden dependency | Primary validation targets are WSL2 Ubuntu and Fedora. Windows host access is secondary only. |

---

## 7. Acceptance Criteria

Migration is complete when:

- Docker Desktop can remain stopped
- WSL2 Ubuntu Docker Engine runs the platform
- Fedora workstation resolves `.local.test` services via CoreDNS
- CoreDNS provides DNS resolution for all `.local.test` hostnames
- nginx routing works for client ingress
- Portkey has no Docker Desktop dependency
- Persistent data is validated (backups restored, services healthy)
- Rollback procedure exists and is documented
- Normal development workflow (VS Code Remote WSL + host Docker) is tested
- Legacy files and Docker Desktop assumptions are removed from docs and repo

---

## 8. Documents to Update

| Document | Action |
|---|---|
| `.env` | Remove `AIASSIST_PATH` (ADR-008 flagged, not yet done). |
| `docs/current-state.md` | Rewrite baseline with WSL2 native Docker as the source of truth; replace dnsmasq references with CoreDNS. |
| `docs/target-state.md` | Update network diagrams; remove Docker Desktop assumptions. |
| `docs/dev-environment.md` | Replace dind workflow with VS Code Remote WSL + host daemon; replace dnsmasq references with CoreDNS. |
| `docs/networking.md` | Replace dnsmasq references with CoreDNS; remove Docker Model Runner hard-coupling references; document model runtime as an external provider. |
| `docs/operations.md` | Update start/shutdown commands for WSL2; add backup/restore runbook sections. |
| `docs/decisions.md` | Add new ADR: WSL2 native Docker Engine as the runtime boundary. Update ADR-002. |
| `docs/runbook-startup.md` | WSL2-specific steps (start WSL, ensure dockerd running, compose order). |
| `docs/runbook-shutdown.md` | WSL2-specific graceful shutdown. |
| Root `docker-compose*.yml` | Delete in Phase 4, after stabilisation. |
| `.devcontainer/devcontainer.json` | Remove dockerComposeFile / dind references; use Remote WSL. |
| `.kilo/plans/1783998200920-saas-deployment-platform-plan.md` | Mark Docker Desktop departure as completed in the design of record. |
| `management/compose.yml` | Add optional operations tooling (Portainer, Dockge). Not required for platform startup. |
