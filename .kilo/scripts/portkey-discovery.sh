#!/bin/bash
# Portkey Routing + Observability Discovery Script
# Run this on the Ubuntu server after deploying the platform stack.
# Usage: bash .kilo/scripts/portkey-discovery.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC} $desc"
    return 0
  else
    echo -e "${RED}FAIL${NC} $desc"
    return 1
  fi
}

fail() {
  echo -e "${RED}FAIL${NC} $1"
}

echo "=== Checkpoint 1: DNS ==="
check "gateway.local.test resolves to VM IP" dig +short gateway.local.test | grep -q '^192\.168\.1\.238$'
check "lf.local.test resolves to VM IP" dig +short lf.local.test | grep -q '^192\.168\.1\.238$'
check "portkey.local.test resolves to VM IP" dig +short portkey.local.test | grep -q '^192\.168\.1\.238$'

echo ""
echo "=== Checkpoint 2: Gateway routing ==="
check "gateway.local.test returns Portkey response" curl -sk https://gateway.local.test/ | grep -qi "AI Gateway says hey"

echo ""
echo "=== Checkpoint 3: Provider routing ==="
RESPONSE=$(curl -sk https://gateway.local.test/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}' || true)
if echo "$RESPONSE" | grep -q '"choices"'; then
  echo -e "${GREEN}PASS${NC} Portkey chat completions endpoint returns choices"
else
  echo -e "${RED}FAIL${NC} Portkey chat completions endpoint did not return choices"
  echo "Response: $RESPONSE"
fi

echo ""
echo "=== Checkpoint 4: Portkey UI discovery (8787) ==="
PORTKEY_CONTAINER=$(docker ps --filter "name=portkey" --format "{{.Names}}" | head -n1)
if [ -z "$PORTKEY_CONTAINER" ]; then
  echo -e "${RED}SKIP${NC} Portkey container not running"
else
  echo "Portkey container: $PORTKEY_CONTAINER"
  check "Portkey listens on 4000" docker exec "$PORTKEY_CONTAINER" ss -lntp | grep -q ':4000'
  check "Portkey listens on 8787" docker exec "$PORTKEY_CONTAINER" ss -lntp | grep -q ':8787' || echo -e "${NC}INFO${NC} No listener on 8787 (UI may not exist)"
  docker exec "$PORTKEY_CONTAINER" curl -s localhost:8787/ || echo -e "${NC}INFO${NC} 8787/ did not return content"
fi

echo ""
echo "=== Checkpoint 5: Docker Model Runner decoupling ==="
if [ -n "$PORTKEY_CONTAINER" ]; then
  check "No extra_hosts on portkey" docker inspect "$PORTKEY_CONTAINER" --format '{{json .HostConfig.ExtraHosts}}' | grep -qv 'null'
  check "No model-runner in generated config" docker exec "$PORTKEY_CONTAINER" cat /app/conf.json | grep -qv 'model-runner'
else
  echo -e "${RED}SKIP${NC} Portkey container not running"
fi

echo ""
echo "=== Checkpoint 6: OTel + OpenObserve ==="
check "OpenObserve reachable" curl -sk https://oo.local.test/ | grep -qi "openobserve"

echo ""
echo "=== Checkpoint 7: Langfuse reachable ==="
check "Langfuse reachable" curl -sk https://lf.local.test/ | grep -qi "langfuse"

echo ""
echo "=== Discovery complete ==="
