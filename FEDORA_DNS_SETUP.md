# Fedora DNS Setup for Local .test Domain Resolution

This guide configures your Fedora system to:
1. Query your server's CoreDNS (port 53) for all `*.local.test` domains
2. Fall back to public DNS (1.1.1.1) for all other domains

## Prerequisites
- Your server is running and accessible via its IP address
- CoreDNS is exposed on port 53 on the server (already configured in this repo)
- The server's CoreDNS is set up to resolve `*.local.test` (via local-test-zones.json)

## Steps

### 1. Find Your Server's IP Address
On the server, run:
```bash
hostname -I  # or ip a
```
Note the IP address (e.g., `192.168.1.100` or `203.0.113.5`).

### 2. Configure Fedora DNS
Run these commands on your Fedora machine:

```bash
# Backup current resolv.conf
sudo cp /etc/resolv.conf /etc/resolv.conf.backup

# Set DNS to query your server's CoreDNS for .local.test, fallback to Cloudflare
sudo tee /etc/resolv.conf > /dev/null <<EOF
nameserver 192.168.1.238
nameserver 1.1.1.1
options edns0 trust-ad
search .
EOF

# Make it immutable (optional but recommended to prevent DHCP overwrites)
# sudo chattr +i /etc/resolv.conf
```

Replace `<SERVER_IP>` with your server's actual IP address.

### 3. Test the Configuration
```bash
# Should resolve to your server's IP (e.g., 192.168.1.238)
dig gitea.local.test @localhost

# Should resolve normally (not your server's IP)
dig google.com @localhost

# Test reverse
dig +short myip.opendns.com @resolver1.opendns.com
```

### 4. Verify CoreDNS is Working on Server
On your server, check:
```bash
# Test internal resolution
dig gitea.local.test @127.0.0.1 -p 53

# Test external resolution
dig google.com @127.0.0.1 -p 53
```

## How It Works
- All DNS queries go to your server's CoreDNS (port 53) first
- CoreDNS checks `local-test-zones.json` for `*.local.test` matches
- If found, returns the server's IP (192.168.1.238)
- If not found (or for non-.local.test domains), forwards to 1.1.1.1
- Your Fedora sees 1.1.1.1 as secondary, but CoreDNS handles forwarding

## Troubleshooting
If resolution fails:
1. Check server firewall: `sudo firewall-cmd --list-ports` (should include 53/tcp,53/udp)
2. Verify CoreDNS is running: `docker ps | grep core_dns`
3. Test from server: `dig @127.0.0.1 -p 53 gitea.local.test`
4. Check Fedora resolv.conf: `cat /etc/resolv.conf`

## To Revert
```bash
sudo cp /etc/resolv.conf.backup /etc/resolv.conf
# or
sudo dhclient -r  # if using DHCP
```

---
*This setup maintains split-horizon DNS: internal .local.domain via your infrastructure, external via public resolvers.*