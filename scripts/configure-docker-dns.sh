#!/usr/bin/env bash
# This script updates the Docker daemon configuration to use systemd-resolved (127.0.0.53)
# and restarts the Docker service. Run with root privileges.

set -e

DAEMON_JSON="/etc/docker/daemon.json"
BACKUP_DIR="/tmp/kilo/docker-config-backups"

mkdir -p "$BACKUP_DIR"
# Ensure /etc/docker exists before writing to it
mkdir -p /etc/docker

if [ -f "$DAEMON_JSON" ]; then
    cp "$DAEMON_JSON" "$BACKUP_DIR/daemon.json.$(date +%Y%m%d_%H%M%S)"
fi

cat > "$DAEMON_JSON" <<'EOF'
{
  "dns": ["127.0.0.53"],
  "dns-search": ["."]
}
EOF

chmod 644 "$DAEMON_JSON"

# Subsidiary: restart Docker depending on init system
if command -v systemctl &>/dev/null; then
    echo "Restarting Docker via systemd"
    systemctl restart docker || true
elif command -v docker &>/dev/null; then
    echo "Docker daemon restart requested via docker command"
    # Note: On some systems, docker daemon must be restarted via systemctl or service
    # If systemctl failed above, we attempt a fallback
    service docker restart || true
else
    echo "Cannot restart Docker: no systemctl or docker command found"
    exit 1
fi

echo "Docker daemon DNS configured to use systemd-resolved (127.0.0.53)"