# Fedora DNS Setup for Local .test Domain Resolution

This guide configures your Fedora system to:
1. Query your server's CoreDNS (port 53) for all `*.local.test` domains
2. Fall back to public DNS (1.1.1.1) for all other domains

## Prerequisites
- Your **server** has systemd-resolved **disabled** and CoreDNS running on port 53
- The server's IP is `192.168.1.238`
- CoreDNS resolves `*.local.test` to your server's IP

## Server Setup (Run ONCE on Ubuntu Server)

```bash
# 1. Stop and disable systemd-resolved (frees port 53 for CoreDNS)
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved

# 2. Remove stub resolv.conf
sudo rm /etc/resolv.conf

# 3. Point server DNS to CoreDNS
sudo tee /etc/resolv.conf > /dev/null <<EOF
nameserver 127.0.0.1
options edns0 trust-ad
search .
EOF

# 4. Rebuild infrastructure
cd ~/projects/aiassistant
make infra-rebuild
```

## Fedora Client Setup (Run on your laptop)

```bash
# Install dnsmasq for split-horizon DNS
sudo dnf install -y dnsmasq

# Configure dnsmasq: forward *.local.test to server's CoreDNS (port 53)
sudo tee /etc/dnsmasq.d/local-test.conf > /dev/null <<EOF
# Forward all *.local.test queries to server's CoreDNS
server=/local.test/192.168.1.238

# Use public DNS for everything else
server=1.1.1.1
server=8.8.8.8

# Listen on localhost only
listen-address=127.0.0.1
port=53
EOF

# Stop systemd-resolved on Fedora too
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved

# Start dnsmasq
sudo systemctl enable dnsmasq
sudo systemctl start dnsmasq

# Point resolv.conf to local dnsmasq
sudo cp /etc/resolv.conf /etc/resolv.conf.backup
sudo tee /etc/resolv.conf > /dev/null <<EOF
nameserver 127.0.0.1
options edns0 trust-ad
search .
EOF
```

## Test the Configuration

```bash
# Should resolve to 192.168.1.238
dig gitea.local.test @127.0.0.1

# Should resolve via public DNS (not 192.168.1.238)
dig google.com @127.0.0.1

# Verify dnsmasq is forwarding correctly
dig *.local.test @127.0.0.1
```

## How It Works
1. **Fedora** sends all DNS to local dnsmasq (127.0.0.1:53)
2. **dnsmasq** checks if query is `*.local.test`
3. If yes → forwards to server's CoreDNS (192.168.1.238:53)
4. If no → forwards to public DNS (1.1.1.1)
5. **Server's CoreDNS** handles `*.local.test` internally, forwards others to 1.1.1.1

## Troubleshooting
- Check dnsmasq: `sudo systemctl status dnsmasq`
- Check CoreDNS on server: `docker ps | grep core_dns`
- Test server DNS: `dig @192.168.1.238 gitea.local.test`

## To Revert
```bash
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq
sudo cp /etc/resolv.conf.backup /etc/resolv.conf
sudo systemctl enable --now systemd-resolved
```