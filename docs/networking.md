# Networking

Four networks, each with a **single owner**. Explicit `name:` makes them globally
consistent across the four Compose projects (no project-prefix surprises).

| Network | Owner file | Attached services |
|---|---|---|
| `infrastructure-network` | `infrastructure/compose.yml` | nginx-proxy, dns, gitea, teamcity-server, teamcity-agent, registry |
| `platform-network` | `platform/compose.yml` | postgres, redis, qdrant, rabbitmq, litellm, otel-collector, langfuse, clickhouse, openobserve, dev-platform-gateway, live-platform-gateway |
| `dev-network` | `environments/dev/compose.yml` | dev app/worker containers + dev-platform-gateway |
| `live-network` | `environments/live/compose.yml` | live app/worker containers + live-platform-gateway |

`infrastructure/compose.yml` declares all four as **real** bridge networks; the platform/dev/live
composes reference `dev-network` and `live-network` as `external: true` (they already exist once
infrastructure is up). **Start infrastructure first.**

## Why this enforces isolation

1. App containers attach ONLY to `dev-network`/`live-network`.
2. They can only reach `platform-network` via their gateway (which is on both `env` + `platform`).
3. The gateway exposes ONLY approved backends (`postgres:5432`, `redis:6379`, `qdrant:6333/6334`,
   `rabbitmq:5672`, `litellm:4000`, `otel-collector:4318`, `langfuse:3000`) and the Host-based
   ingress for `*.dev.local.test` / `*.live.local.test`.
4. `dev-platform-gateway` has NO route to `live-network`; `live-platform-gateway` has NO route to
   `dev-network`. There is no path between the two environments.
5. `nginx-proxy` attaches only to infra+platform and proxies client traffic to the gateways — it
   never touches app containers directly.

## Gateway mechanics

Each gateway is `nginx:alpine` with:
- a `stream {}` block forwarding TCP ports to platform backends, and
- an `http {}` block doing Host-based ingress to app containers on the env network.

```
app (env)  →  <env>-platform-gateway:<port>  →  platform service
client     →  nginx-proxy                     →  <env>-platform-gateway (http)  →  app (env)
```

Host header is preserved end-to-end (`proxy_set_header Host $host`). Late DNS resolution uses
`resolver 127.0.0.11` with the `$upstream` variable pattern so the gateway survives apps starting
after it.

## DNS

`dnsmasq` maps `*.local.test → 127.0.0.1` (host). The wildcard already covers `.dev.local.test` /
`.live.local.test`; explicit `address=/.dev.local.test/...` and `address=/.live.local.test/...`
lines are added for operator clarity. dnsmasq needs `CAP_NET_ADMIN`; on Ubuntu/WSL2 it may compete
with `systemd-resolved` on port 53 — stop/disable `systemd-resolved` or rebind if startup fails.

## Docker Model Runner

Host-local; apps + litellm reach it via `extra_hosts: model-runner.docker.internal:host-gateway`.
Not published to LAN. Works from any network.

## Private registry trust

`registry.local.test` TLS is terminated by nginx-proxy using the `local.test` cert (covers
`*.local.test`). For host-context pulls (TeamCity agent uses the host Docker daemon), install the
`local.test` CA into the Docker trust store:

```
mkdir -p /etc/docker/certs.d/registry.local.test
cp <local.test CA>.crt /etc/docker/certs.d/registry.local.test/ca.crt
```

Or, as a documented trade-off, add `registry.local.test` to `insecure-registries` in
`/etc/docker/daemon.json`. Basic auth is enforced by the registry container.
