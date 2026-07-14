#!/usr/bin/env bash
# Integration Tests — exercised against the DEV tier after deploy-dev.
# Add real smoke/contract/e2e checks here. Fails the pipeline on any error.
set -euo pipefail

BASE="${AGENT_DEV_BASE:-https://agent.dev.local.test}"
API="${API_DEV_BASE:-https://api.dev.local.test}"
LG="${LANGGRAPH_DEV_BASE:-https://langgraph.dev.local.test}"

echo "[integration] base=$BASE"

check() {
  local name="$1"; local url="$2"
  if curl -fsS --max-time 15 "$url" >/dev/null 2>&1; then
    echo "  [ok] $name -> $url"
  else
    echo "  [FAIL] $name -> $url"; return 1
  fi
}

check "control-center-ui" "$BASE/"
check "workflow-engine"   "$API/health"
check "langgraph"         "$LG/ok"

# Add contract / e2e / Playwright steps here.
echo "[integration] passed."
