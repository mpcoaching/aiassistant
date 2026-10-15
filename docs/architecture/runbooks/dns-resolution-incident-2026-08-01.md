# DNS Resolution Incident Postmortem

**Date:** 2026-08-01  
**Systems:** Ubuntu Server (CoreDNS), Fedora Laptop (DNS Client)

## Problem
Domain resolution for `*.local.test` was broken across the entire infrastructure. Commands like `dig gitea.local.test` returned NXDOMAIN or connection refused errors.

## Root Causes
1. **Invalid CoreDNS syntax**: The CoreFile used a nested block structure (`local.test { ... }` inside `:53 { ... }`), which CoreDNS does not support. The correct approach is separate server blocks or the `hosts` plugin.
2. **Missing zone file**: The CoreFile referenced `/etc/coredns/local.test.zone` but the volume mount was not properly aligned with the filesystem.
3. **Docker not in PATH**: Commands were being executed in an environment where Docker was unavailable, leading to failed restarts and outdated configs.
4. **systemd-resolved conflict**: Ubuntu’s `systemd-resolved` occupied port 53, preventing CoreDNS from binding successfully.
5. **DNS fallback misconfiguration**: No reliable fallback existed if CoreDNS became unavailable.

## Fixes Applied

### CoreDNS CoreFile (`/infrastructure/configs/coredns/Corefile`)
- Replaced invalid `local.test { file ... }` block with a valid `hosts` plugin using explicit domain records.
- Used a single `:53 { } ` server block with `forward . 1.1.1.1 8.8.8.8` for internet traffic.
- Removed dependency on external zone files entirely.

### Docker Compose (`/infrastructure/compose.yml`)
- Ensured `CoreFile` is the only volume mounted into the CoreDNS container at `/etc/coredns/Corefile`.
- Removed obsolete zone file mount (`./configs/coredns/local.test.zone`).

### Fedora Laptop DNS
- Created a dedicated configuration file `/etc/dnsmasq.d/local-test.conf` to implement split DNS.
- Set `server=/local.test/<server_ip>` to forward only `.local.test` queries to the Ubuntu server.
- Set `server=1.1.1.1` for all other queries.
- Switched `/etc/resolv.conf` to point to `127.0.0.1` (localhost) so dnsmasq intercepts all queries.
- Stopped `systemd-resolved` to prevent conflicts.
- Restarted `dnsmasq` to apply the new configuration.

## Permanent Fix
All changes are now committed and pushed to GitHub (`commit 0193152`). The setup uses:
- **CoreDNS** on Ubuntu server (listening on port 53)
- **dnsmasq** on Fedora laptop (for split DNS)
- **Public DNS fallback** (1.1.1.1) for internet resolution

## Validation Steps
Run from either machine:
```bash
dig gitea.local.test +short      # Expected: 192.168.1.238
dig google.com +short           # Expected: public IP
```

## Prevention Checklist
- [x] CoreFile syntax validated manually before deployment (`coredns -conf /path/to/Corefile`)
- [x] Docker available in PATH when applying infrastructure changes
- [x] systemd-resolved stopped/disabled before CoreDNS startup
- [x] Split DNS configured via dnsmasq on client machines
- [x] Changes pushed to GitHub before running `make infra-rebuild`