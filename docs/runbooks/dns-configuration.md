# DNS Resolution for *.local.test Domains

## Problem

The Fedora laptop cannot access services running on the Ubuntu server (192.168.1.238) via their `*.local.test` hostnames (e.g., `gitea.local.test`, `n8n-sandbox.local.test`, `searxng.local.test`).

## Root Cause

1. **Ubuntu Server** runs CoreDNS (`infra_dns` container) which is authoritative for the `local.test` zone
2. CoreDNS serves all `*.local.test` hostnames with IP `192.168.1.238`
3. **Fedora laptop** uses its own DNS resolvers (8.8.8.8, 1.1.1.1, 192.168.1.1) which do NOT know about `*.local.test` domains
4. Without using Ubuntu's CoreDNS as a DNS resolver, `*.local.test` domains cannot be resolved

## Permanent Solution

Configure the Fedora laptop to use Ubuntu's CoreDNS (`192.168.1.238`) as its primary DNS resolver.

### Step 1: Configure NetworkManager to not manage DNS

```bash
sudo mkdir -p /etc/NetworkManager/conf.d
sudo tee /etc/NetworkManager/conf.d/dns.conf << 'EOF'
[main]
dns=unmanaged
EOF
sudo systemctl restart NetworkManager
```

### Step 2: Set permanent DNS resolver configuration

```bash
sudo tee /etc/resolv.conf << 'EOF'
# Fedora laptop DNS - use Ubuntu's CoreDNS first for *.local.test
nameserver 192.168.1.238
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF
```

**Note:** With `dns=unmanaged` in NetworkManager, `/etc/resolv.conf` will not be overwritten on reboot or network changes.

### Step 3: Verify the fix

```bash
# Test DNS resolution
nslookup gitea.local.test 192.168.1.238
nslookup n8n-sandbox.local.test 192.168.1.238

# Test browser accessibility
curl -s -o /dev/null -w "%{http_code}" http://gitea.local.test:3000/
curl -s -o /dev/null -w "%{http_code}" http://n8n-sandbox.local.test:5679/healthz
curl -s -o /dev/null -w "%{http_code}" http://searxng.local.test:8080/healthz
curl -s -o /dev/null -w "%{http_code}" http://woodpecker.local.test:8000/
```

All should return `200`.

## Services Running on Ubuntu Server

All services are accessible via `*.local.test` hostnames:

| Service | Hostname | Port | Status |
|---------|----------|------|--------|
| Gitea | `gitea.local.test` | 3000 | Running |
| Woodpecker Server | `woodpecker.local.test` | 8000 | Running |
| SearXNG | `searxng.local.test` | 8080 | Running |
| n8n (production) | `n8n.local.test` | 5678 | Running |
| n8n-sandbox | `n8n-sandbox.local.test` | 5679 | Running |
| Portkey | `portkey.local.test` | 4000 | Running |
| Langfuse | `langfuse.local.test` | 3000 | Running |
| Registry | `registry.local.test` | 5000 | Running |
| OpenObserve | `openobserve.local.test` | 8080 | Running |

## Why This Fix Works

1. **Ubuntu's CoreDNS** (`192.168.1.238:53`) is authoritative for `local.test` zone
2. It serves all `*.local.test` hostnames with IP `192.168.1.238`
3. By making Fedora use Ubuntu's CoreDNS as its primary DNS resolver, all `*.local.test` domains resolve automatically
4. No manual `/etc/hosts` maintenance needed
5. Browser accessibility works consistently

## Troubleshooting

If DNS resolution still fails after applying the fix:

1. Verify CoreDNS is running on Ubuntu:
   ```bash
   docker ps | grep infra_dns
   ```

2. Verify CoreDNS is listening on port 53:
   ```bash
   netstat -tulpn | grep 53
   ```

3. Test DNS resolution directly:
   ```bash
   nslookup gitea.local.test 192.168.1.238
   ```

4. Check if there's a firewall blocking port 53:
   ```bash
   sudo firewall-cmd --list-ports | grep 53
   ```

## Notes

- This configuration persists across reboots because NetworkManager is configured to not manage DNS
- `/etc/resolv.conf` is a symlink to `/run/systemd/resolve/resolv.conf` on some systems; if it gets overwritten, reapply the fix
- The Ubuntu server's CoreDNS must be running for this to work; if CoreDNS is stopped, `*.local.test` domains will not resolve