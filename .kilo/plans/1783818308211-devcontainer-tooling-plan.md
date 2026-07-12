# Devcontainer Tooling & Local/Server Environment Split

## Context

The local devcontainer (`.devcontainer/devcontainer.json`) launches via the `workspace`
service in `docker-compose.yml`, but that service uses a bare `ubuntu:24.04` image with
**no Node, no Python, and no Docker CLI** — which is why `node`, `npm`, and `docker` are
all missing inside this environment, and why local `vitest`/`docker compose config`
validation couldn't run earlier.

Goal: make local development "slick" while keeping the full stack off the laptop. Two
environments, cleanly separated:

- **Local laptop (you + Kilo editing):** a devcontainer with Node 20 + npm + Python 3.11 +
  pytest + Docker CLI, plus a **Docker-in-Docker (dind) sandbox sidecar**. The sandbox is
  used only to spin up **one service at a time** for fast integration testing — never the
  whole stack.
- **Remote server (the real solution):** runs `docker-compose.platform.yml` +
  `docker-compose.yml` together. **Gitea is the config/VCS source of truth and TeamCity
  runs the actual `docker compose` deploys** via its agent (the existing plan's controller).
  Kilo edits repo configs → pushes to Gitea → TeamCity deploys. No separate controller
  container is needed.

## Locked Decisions

- Local Docker = **dind sidecar** (isolated from laptop host; one service at a time).
- Remote controller = **Gitea + TeamCity** (already in `docker-compose.platform.yml`).
- Devcontainer toolchain = **Node 20 + npm (keep existing lockfile) + Python 3.11 + pytest/pytest-cov + docker CLI**.

## Tasks

### 1. Devcontainer image (`.devcontainer/Dockerfile`)
Create a buildable image (base `ubuntu:24.04`) installing:
- Node 20 via NodeSource + `npm` (no lockfile change to the UI).
- Python 3.11 + `pip` → `pytest`, `pytest-cov` (for the `workflow-runner` coverage gate).
- Docker CLI **client only** (talks to the dind sidecar; no dockerd in this image).
- `git`, `gh`, `curl`.
Keep `remoteUser: root` (matches existing devcontainer).

### 2. Dev-only compose (`docker-compose.dev.yml`) — laptop only
- Move the `workspace` service here (remove it from `docker-compose.yml` so the server
  stack stays clean). `workspace` builds from `.devcontainer/Dockerfile`, keeps the existing
  volume mounts (`.:/aiassistant`, `configs`), sets `DOCKER_HOST=tcp://docker-dind:2375`,
  and `depends_on: [docker-dind]`.
- Add `docker-dind` sidecar: `image: docker:dind`, `privileged: true`,
  command `dockerd-entrypoint.sh dockerd --host=tcp://0.0.0.0:2375 --tls=false`, expose `2375`.
- **Override networks**: redefine `ai_net` and `monitoring-net` as local (non-`external`)
  so a single service can run inside the sandbox without the server's real networks.
- This file is never used on the server.

### 3. Update `.devcontainer/devcontainer.json`
- `dockerComposeFile`: array `["../docker-compose.yml", "../docker-compose.dev.yml"]`
  (merged compose still exposes `workspace` + local networks).
- `service: workspace` (now defined in the dev file).
- `remoteEnv`: `{ "DOCKER_HOST": "tcp://docker-dind:2375", "DOCKER_TLS_VERIFY": "" }`.
- Keep `workspaceFolder: /aiassistant`, `remoteUser: root`.
Result: after launch, `docker`, `node`, `npm`, `pytest` all work; `docker` hits the
sandbox, not the laptop host.

### 4. Single-service sandbox workflow (microservices rule)
Document the loop in `docs/dev-environment.md`:
```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up <one-service>
```
Networks are local in the sandbox, so e.g. `up workflow-engine` (with its `wait_for.py`
entrypoint waiting on `postgres:5432` — which is NOT in the sandbox) only works if that
dep is also started or mocked. **Guidance: for local iteration, bring up at most the one
service under edit + its direct dependency**; full multi-service testing belongs on the
server. Keep it explicit that the laptop does NOT run the full stack.

### 5. Runbook `docs/dev-environment.md`
Cover: (a) local = devcontainer + dind single-service testing + `npm test` / `pytest`;
(b) server = platform + agentic composed together, Gitea holds the repo, TeamCity BC1
(test+ratchet) / BC2 (promote-dev) / BC3 (promote-live) deploy; (c) start order — platform
first (`docker-compose.platform.yml`), then agentic (`docker-compose.yml`); (d) how Kilo
deploys: edit → push Gitea → TeamCity agent runs `docker compose` on the server daemon.

### 6. `.gitignore`
Add `node_modules/`, `coverage/`, `playwright-results.xml`, `.pytest_cache/` (dev/CI
artifacts). Note: `.env` already must stay out of git (contains secrets).

### 7. Final validation
- YAML parse both compose files + the dev override (`python3 -c "import yaml;yaml.safe_load"`).
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml config` (run inside the
  devcontainer against dind, or on the server) to confirm no cross-project `depends_on` and
  networks resolve.
- Confirm `node -v`, `npm -v`, `python3 -V`, `pytest --version`, `docker version` (client)
  succeed inside the rebuilt devcontainer.

## Files
- **Create** `.devcontainer/Dockerfile`
- **Create** `docker-compose.dev.yml`
- **Edit** `.devcontainer/devcontainer.json`
- **Edit** `docker-compose.yml` (remove `workspace` service block; leave agentic stack intact)
- **Create** `docs/dev-environment.md`
- **Edit** `.gitignore`

## Risks / Notes
- dind requires `privileged` on the outer Docker (fine on Docker Desktop / normal Linux
  Docker; document if a restricted host is used).
- TLS disabled on dind is dev-only and sandbox-isolated — acceptable; do NOT carry this to
  the server.
- Keep `ai_net` name exactly `ai_net` everywhere (hardcoded in nginx resolver + openhands env).
- The agentic services' `wait_for.py` entrypoints assume platform deps (`postgres`,
  `rabbitmq`); in the sandbox those must be started or the service will block — expected.

## Out of Scope
- Migrating the UI from npm to pnpm (avoids lockfile churn).
- Building a dedicated controller container (Gitea+TeamCity already cover it).
- Running the full stack on the laptop.
