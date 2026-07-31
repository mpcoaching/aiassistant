#!/usr/bin/env bash
set -e

SERVER_IP="${SERVER_IP:-192.168.1.238}"
DAEMON_JSON="/etc/docker/daemon.json"
BACKUP_DIR="/tmp/kilo/docker-config-backups"

echo "Configuring Docker daemon to use CoreDNS at ${SERVER_IP}"

mkdir -p "$BACKUP_DIR"
mkdir -p /etc/docker

if [ -f "$DAEMON_JSON" ]; then
    cp "$DAEMON_JSON" "$BACKUP_DIR/daemon.json.$(date +%Y%m%d_%H%M%S)"
fi

cat > "$DAEMON_JSON" <<EOF
{
  "dns": ["${SERVER_IP}"],
  "dns-search": ["."]
}
EOF

chmod 644 "$DAEMON_JSON"

if command -v systemctl &>/dev/null; then
    echo "Restarting Docker via systemd"
    systemctl restart docker || true
elif command -v docker &>/dev/null; then
    echo "Docker daemon restart requested via docker command"
    service docker restart || true
else
    echo "Cannot restart Docker: no systemctl or docker command found"
    exit 1
fi

echo "Docker daemon DNS configured to use CoreDNS (${SERVER_IP})"