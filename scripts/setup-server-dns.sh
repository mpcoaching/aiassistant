#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="192.168.1.238"
ZONE_FILE="/home/martinp/Documents/projects/aiassistant/infrastructure/configs/coredns/local.test.zone"
COREFILE="/home/martinp/Documents/projects/aiassistant/infrastructure/configs/coredns/Corefile"
PROJECT_DIR="/home/martinp/Documents/projects/aiassistant"

echo "=== Server DNS Setup ==="
echo "Server IP: $SERVER_IP"

# 1. Stop systemd-resolved (frees port 53 for CoreDNS)
echo "[1/7] Stopping systemd-resolved..."
systemctl stop systemd-resolved || true
systemctl disable systemd-resolved || true

# 2. Point host DNS to CoreDNS (runs on host port 53 via container)
echo "[2/7] Configuring host DNS to point to CoreDNS (127.0.0.1)..."
rm -f /etc/resolv.conf
cat > /etc/resolv.conf <<EOF
nameserver 127.0.0.1
options edns0 trust-ad
search .
EOF

# 3. Ensure BIND zone file exists
echo "[3/7] Verifying zone file..."
if [ ! -f "$ZONE_FILE" ]; then
    echo "ERROR: Zone file not found at $ZONE_FILE"
    exit 1
fi

# 4. Ensure Corefile exists
echo "[4/7] Verifying Corefile..."
if [ ! -f "$COREFILE" ]; then
    echo "ERROR: Corefile not found at $COREFILE"
    exit 1
fi

# 5. Configure Docker daemon to use host IP (not 127.0.0.1) for container DNS
echo "[5/7] Configuring Docker daemon DNS to use CoreDNS via host IP..."
mkdir -p /etc/docker
BACKUP_DIR="/tmp/kilo/docker-config-backups"
mkdir -p "$BACKUP_DIR"
if [ -f /etc/docker/daemon.json ]; then
    cp /etc/docker/daemon.json "$BACKUP_DIR/daemon.json.$(date +%Y%m%d_%H%M%S)"
fi
cat > /etc/docker/daemon.json <<EOF
{
  "dns": ["${SERVER_IP}"],
  "dns-search": ["."]
}
EOF
chmod 644 /etc/docker/daemon.json

# 6. Restart Docker to apply daemon.json
echo "[6/7] Restarting Docker..."
systemctl restart docker

# 7. Start infrastructure
echo "[7/7] Starting infrastructure..."
cd "$PROJECT_DIR"
docker compose -f infrastructure/compose.yml --env-file .env up -d

echo ""
echo "=== Setup Complete ==="
echo "Verify with:"
echo "  dig gitea.local.test @127.0.0.1 +short"
echo "  dig google.com @127.0.0.1 +short"
