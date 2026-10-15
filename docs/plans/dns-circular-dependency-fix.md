# DNS Circular Dependency Fix Plan

## Timestamp
2026-07-30

## Error
During `make infra-rebuild`, Docker fails to pull or build images with:

```
dns lookup registry-1.docker.io on 127.0.0.1:53: read udp 127.0.0.1:35444->127.0.0.1:53: read: connection refused
```

## Root Cause

CoreDNS in the infrastructure compose stack was exposed on host port 53:

```yaml
# OLD (broken)
  dns:
    image: coredns/coredns:1.11.1
    container_name: infra_dns
    ports:
      - "53:53/udp"
      - "53:53/tcp"
    command: -conf /Corefile
    volumes:
      - ./configs/coredns/Corefile:/Corefile:ro
    cap_add:
      - NET_ADMIN
    networks:
      - infrastructure-network
    restart: unless-stopped
```

The `ports` mapping (`53:53/udp` and `53:53/tcp`) makes CoreDNS listen on `127.0.0.1:53` on the Docker host. Docker daemon uses `127.0.0.1:53` as its DNS resolver for image pull and build operations. When `docker compose down` stops CoreDNS, `127.0.0.1:53` becomes unavailable, and Docker cannot resolve any hostnames, including `registry-1.docker.io` needed to pull base images. This creates a circular dependency: CoreDNS must be running for Docker to work, but Docker is needed to start CoreDNS.

## Investigation Evidence

The following was verified on the server:

1. **No `daemon.json` exists** — `/etc/docker/daemon.json` does not exist. Docker daemon has no explicit DNS override.
2. **No systemd drop-ins** — No Docker service override files exist anywhere (`/etc/systemd/system/docker*`, `/lib/systemd/system/docker*`).
3. **systemd-resolved works correctly** — `resolvectl status` shows `DNS=192.168.1.238` with `FallbackDNS=1.1.1.1 8.8.8.8` and `Domains=~local.test`. The stub resolver listens at `127.0.0.53`.
4. **`/etc/resolv.conf` correctly points to systemd-resolved** — symlink to `stub-resolv.conf`, which points to `127.0.0.53`.
5. **No NetworkManager DNS interference** — NetworkManager DNS config is empty/default.
6. **No dnsmasq or other DNS forwarder running** — Only `systemd-resolved` listens on port 53 at `127.0.0.53-54`.
7. **CoreDNS is the only process at `127.0.0.1:53`** when infrastructure is running, because of the `ports` mapping.

**Conclusion**: Docker daemon picks up `127.0.0.1:53` (CoreDNS) when the infrastructure stack is up. When the stack is torn down (`docker compose down`), port 53 is freed. Docker daemon can no longer resolve any hostnames. Image pulls fail. Infrastructure rebuild deadlocks.

The fix is to remove the `ports` mapping so CoreDNS is no longer the listener at `127.0.0.1:53`. Docker daemon will then use the system DNS chain (systemd-resolved at `127.0.0.53`) which works independently of CoreDNS availability.

## Fix Applied

### infrastructure/compose.yml — CoreDNS service

Removed `ports` and `cap_add` from the CoreDNS service definition. CoreDNS now operates exclusively within the `infrastructure-network` Docker network, accessible by service name `dns` from other containers on that network.

```yaml
# NEW (fixed)
  # ----- DNS: internal only — resolves *.local.test for Docker network containers -----
  # Not exposed on the host. Docker's built-in DNS (127.0.0.11) handles inter-container
  # service discovery. CoreDNS is only for *.local.test FQDN resolution within the
  # infrastructure-network. Docker pull/build use system DNS and must never depend on
  # CoreDNS being up.
  dns:
    image: coredns/coredns:1.11.1
    container_name: infra_dns
    command: -conf /Corefile
    volumes:
      - ./configs/coredns/Corefile:/Corefile:ro
    networks:
      - infrastructure-network
    restart: unless-stopped
```

**What changed**:
- Removed `ports: ["53:53/udp", "53:53/tcp"]` — CoreDNS no longer binds to host port 53
- Removed `cap_add: [NET_ADMIN]` — unnecessary since no host port binding
- Updated comments to clarify CoreDNS scope

### makefile — infra-rebuild target

Updated to use `docker compose ... up -d --build` which pulls images and rebuilds in a single operation, eliminating the broken two-step approach.

```makefile
infra-rebuild:
	git pull
	docker compose -f infrastructure/compose.yml --env-file .env up -d --build
```

## DNS Architecture

### Host-Level DNS (Layer 1)

```
Application → /etc/resolv.conf → systemd-resolved stub (127.0.0.53)
  → systemd-resolved forwards to configured servers in /etc/systemd/resolved.conf:
      Primary DNS:   192.168.1.238 (router)
      Fallback DNS:  1.1.1.1, 8.8.8.8
  → Domains=~local.test routing for platform-specific domains
```

Docker daemon reads `/etc/resolv.conf` → uses `127.0.0.53` (systemd-resolved) → routes to upstream DNS. This chain is independent of CoreDNS availability.

### Docker Container DNS (Layer 2)

Docker containers on compose networks use Docker's embedded DNS at `127.0.0.11` for service name resolution. No per-service `dns:` override is needed.

For `*.local.test` resolution within Docker networks, containers use CoreDNS via the `dns` service name on the shared `infrastructure-network`.

### `.local.test` Host-Level Access

`*.local.test` domain resolution for host applications (including the Fedora laptop) uses the host's DNS resolver chain (systemd-resolved → router → upstream). The `Domains=~local.test` setting in `/etc/systemd/resolved.conf` ensures `*.local.test` queries are routed through the configured DNS servers. This is independent of Docker and CoreDNS.

## Infrastructure Layers

```
Host Infrastructure (Layer 1)
├── Operating system
├── Docker Engine
├── Docker networking
├── systemd-resolved (127.0.0.53)
└── Upstream DNS (192.168.1.238, 1.1.1.1, 8.8.8.8)

Platform Infrastructure (Layer 2)
├── CoreDNS — *.local.test for Docker networks ONLY
├── nginx-proxy
├── redis
└── registry

Platform Services (Layer 3)
├── configuration-manager — depends on redis
├── gitea
├── portkey
└── gitea-runner — depends on gitea

Capabilities (Layer 4)
└── ci-worker — depends on configuration-manager via HTTP
```

Dependencies flow strictly downward. No layer depends on a higher layer. CoreDNS (Layer 2) is not a prerequisite for Docker operations (Layer 1).

## Validation

### Verify CoreDNS is no longer on host port 53

```bash
# Before fix (problem): CoreDNS was at 127.0.0.1:53
ss -tlnp | grep ':53'   # showed 127.0.0.1:53 (CoreDNS)

# After fix (resolved): CoreDNS not on host port 53
ss -tlnp | grep ':53'   # shows only 127.0.0.53:53 (systemd-resolved)
```

### Verify Docker DNS works independently of CoreDNS

```bash
# With infrastructure stack running
docker build -t platform/configuration-manager:latest packages/configuration/
# Should succeed — Docker uses system DNS (127.0.0.53), not CoreDNS (was 127.0.0.1)
```

### Verify *.local.test resolves within Docker containers

```bash
# CoreDNS accessible from Docker network
docker run --rm --network infrastructure-network alpine \
  nslookup gitea.local.test dns.infrastructure-network
```

### Verify host-level *.local.test resolution works

```bash
# Host uses systemd-resolved for .local.test
curl -I https://gitea.local.test  # should succeed from host
curl -I https://gitea.local.test  # should succeed from laptop
```

### Full rebuild sequence

```bash
make infra-rebuild
```

Expected: Completes successfully without DNS resolution errors. Docker pull/build operations work even when CoreDNS has been stopped (because Docker uses system DNS, not CoreDNS).