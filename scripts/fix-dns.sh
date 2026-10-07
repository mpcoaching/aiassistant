#!/bin/bash
# Permanent DNS fix for Fedora laptop to access *.local.test domains
# Run this script with: sudo bash fix-dns.sh

set -euo pipefail

echo "=== Configuring Fedora laptop DNS for *.local.test access ==="

# Step 1: Configure NetworkManager to not manage DNS
echo "Step 1: Configuring NetworkManager..."
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/dns.conf << 'NMEOF'
[main]
dns=unmanaged
NMEOF

# Step 2: Set permanent DNS resolver configuration
echo "Step 2: Setting DNS resolver configuration..."
cat > /etc/resolv.conf << 'RESEOF'
# Fedora laptop DNS - use Ubuntu's CoreDNS first for *.local.test
nameserver 192.168.1.238
nameserver 1.1.1.1
nameserver 8.8.8.8
RESEOF

# Step 3: Restart NetworkManager
echo "Step 3: Restarting NetworkManager..."
systemctl restart NetworkManager

# Step 4: Verify the fix
echo ""
echo "=== Verifying DNS configuration ==="
echo "Current /etc/resolv.conf:"
cat /etc/resolv.conf
echo ""
echo "Testing DNS resolution:"
nslookup gitea.local.test 192.168.1.238 || echo "WARNING: DNS resolution test failed"
nslookup n8n-sandbox.local.test 192.168.1.238 || echo "WARNING: DNS resolution test failed"

echo ""
echo "=== DNS configuration complete ==="
echo "You can now access services via *.local.test hostnames:"
echo "  - http://gitea.local.test:3000"
echo "  - http://n8n-sandbox.local.test:5679"
echo "  - http://searxng.local.test:8080"
echo "  - http://woodpecker.local.test:8000"