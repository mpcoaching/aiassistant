#!/usr/bin/env bash
# Phase 1 smoke test for the Portkey AI Gateway (ADR-009).
# Validates end-to-end invocation through the platform gateway.
#
# Usage (from a host that can reach the gateway):
#   bash platform/tests/smoke-portkey.sh            # via localhost (port published)
#   GATEWAY=dev-platform-gateway:4000 \
#     bash platform/tests/smoke-portkey.sh          # via the env gateway
#
# Env:
#   GATEWAY        host:port of the gateway surface (default localhost:4000)
#   PORTKEY_KEY    master key (default reads PORTKEY_MASTER_KEY from .env)
set -euo pipefail

GATEWAY="${GATEWAY:-localhost:4000}"
KEY="${PORTKEY_KEY:-${PORTKEY_MASTER_KEY:-pk-super-secret-portkey-keymaster-keep-oot}}"

if [ -f .env ] && [ -z "${PORTKEY_MASTER_KEY:-}" ]; then
  # shellcheck disable=SC1091
  export "$(grep -E '^PORTKEY_MASTER_KEY=' .env | head -1)"
  KEY="${PORTKEY_MASTER_KEY}"
fi

echo "==> Gateway liveness: http://${GATEWAY}/"
curl -fsS "http://${GATEWAY}/" && echo

echo "==> Models list (requires master key): http://${GATEWAY}/v1/models"
curl -fsS "http://${GATEWAY}/v1/models" \
  -H "x-portkey-api-key: ${KEY}" | head -c 400
echo

# Smoke completion: Groq cloud first, then local fallback via @slug/model form.
echo "==> Smoke chat completion via Groq (model: @groq-cloud/llama-3.3-70b-versatile)"
curl -fsS "http://${GATEWAY}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-portkey-api-key: ${KEY}" \
  -d '{
    "model": "@groq-cloud/llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    "max_tokens": 16
  }' | head -c 600
echo

echo "Smoke test complete."
