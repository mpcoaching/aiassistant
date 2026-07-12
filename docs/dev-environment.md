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

## Accessing the server from client machines

The full stack runs **on the server** (192.168.1.30). Access dev/live environments via `.local.test` hostnames.

### Option A — Automatic DNS (systemd-resolved + Docker dnsmasq)

Configure the system resolver to forward `.local.test` queries to the dnsmasq container.

#### WSL2 Ubuntu server

1. dnsmasq must be reachable without conflicting with systemd-resolved's stub listener. Use the published port 5353:

```bash
docker compose -f docker-compose.platform.yml up -d
curl -s http://localhost:5353  # should return dnsmasq "no such domain"
```

2. Configure systemd-resolved for split-DNS forwarding. Edit `/etc/systemd/resolved.conf`:

```ini
[Resolve]
DNS=127.0.0.1#5353
Domains=~local.test
```

3. Restart and verify:

```bash
sudo systemctl restart systemd-resolved
resolvectl query gitea.local.test
```

#### Fedora laptop

1. Use NetworkManager split-DNS so the VPN/lan connection handles `.local.test` specially:

```bash
CONN=$(nmcli -g UUID con show --active | head -n1)
nmcli con mod "$CONN" ipv4.ignore-auto-dns yes ipv4.dns "192.168.1.30" ipv4.dns-search "~local.test"
nmcli con mod "$CONN" ipv6.ignore-auto-dns yes ipv6.dns "192.168.1.30" ipv6.dns-search "~local.test"
nmcli con up "$CONN"
```

2. Verify:

```bash
dig gitea.local.test
curl -I http://gitea.local.test
```

### Option B — Hosts file (cross-platform fallback)

Supports portably. Add to `C:\Windows\System32\drivers\etc\hosts` or `/etc/hosts`:

```
192.168.1.30  gitea.local.test teamcity.local.test control-center.local.test dev.local.test qdrant.local.test langfuse.local.test litellm.local.test langgraph.local.test workflow-engine.local.test otel.local.test openobserve.local.test n8n.local.test
```

Then browse to e.g. `http://gitea.local.test` (port 80, proxied by nginx).
