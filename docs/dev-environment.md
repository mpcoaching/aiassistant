# Dev Environment — Local vs Server

## Environments

### Local (this laptop)
VS Code devcontainer with Node 20, npm, Python 3 + pytest/pytest-cov, Docker CLI (client).
The Docker client talks to a **Docker-in-Docker (dind) sandbox sidecar** launched
alongside the workspace container — it does NOT use the laptop's Docker daemon.
The sandbox is isolated and can run at most one service at a time.

Validations you should run locally:
- `npm test` (vitest units) from `agentic/src/control-center-ui`
- `pytest` from `agentic/src/workflow-runner`
- `playwright test` (e2e slice) from `agentic/src/control-center-ui`
- Single-service integration: see the sandbox workflow below.

**Single-service sandbox workflow (the microservices rule)**
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up <one-service>
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```
Networks are local in the sandbox (files override `external: true` to named local
networks). Platform services like `postgres` are NOT in the sandbox by default. If
the service you're testing needs a dependency, bring up just that one dependency too.
Never spin up the full stack locally.

### Server (the real solution)
The server runs the full `docker-compose.platform.yml` + `docker-compose.yml` together.
This machine is the "controller environment" accessed (and edited) by Kilo.

Start order on the server:
1) `docker compose -f docker-compose.platform.yml up -d`
2) `docker compose -f docker-compose.yml up -d`

The **platform** owns `ai_net` and `monitoring-net` (explicitly named so the agentic
stack can attach as `external: true`). It hosts: nginx-proxy, dns, postgres,
db-bootstrapper, migrate, qdrant, rabbitmq, redis, langfuse, clickhouse, otel,
openobserve, plus **Gitea** (repo/config source of truth) and **TeamCity server + agent**
(CI that runs deploys on the server docker daemon).

The **agentic** stack owns the live and dev tiers (`control-center-ui/b`, `workflow-engine`,
`langgraph`, `litellm`, `dev-controller`, `dev-workflow-engine`, `dev-langgraph`,
`dev-litellm`) plus optional tools (openhands, aider, autogen-studio, n8n). It declares
the networks `external: true` and connects to platform services by hostname
(`postgres`, `rabbitmq`, `redis-agents`).

## How Kilo deploys
1. Edit config in the repo.
2. Push to **Gitea** on the server (`gitea.local.test`).
3. **TeamCity** build configs (in `infra/ci/teamcity-build-configs.md`) trigger deploys
   via its agent (which mounts the host docker socket).
   - BC1: test + ratchet coverage gate
   - BC2: promote to dev (`dev.local.test`)
   - BC3: promote to live (`control-center.local.test`) — manual gate

## Toolchain versions
- Node: 20, npm (no pnpm/yarn)
- Python: 3.x, pytest + pytest-cov
- Docker: client-only in devcontainer; talks to dind sidecar.
