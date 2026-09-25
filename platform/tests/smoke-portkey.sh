#!/usr/bin/env bash
# Smoke test for the Portkey AI Gateway (ADR-009).
# Validates end-to-end invocation through the platform gateway.
#
# Usage:
#   GATEWAY=localhost:4000 bash platform/tests/smoke-portkey.sh
#   GATEWAY=172.21.0.7:4000 bash platform/tests/smoke-portkey.sh
set -euo pipefail

GATEWAY="${GATEWAY:-localhost:4000}"
KEY="${PORTKEY_KEY:-pk-super-secret-portkey-keymaster-keep-oot}"
# Inline config: fallback to Ollama local model (qwen2.5-coder:7b)
CONFIG='{"strategy":{"mode":"fallback"},"targets":[{"provider":"openai","api_key":"ollama","custom_host":"http://192.168.1.68:11434/v1","override_params":{"model":"qwen2.5-coder:7b"}}]}'

echo "==> Gateway liveness: http://${GATEWAY}/"
curl -fsS "http://${GATEWAY}/" && echo

echo "==> Smoke chat completion via Ollama (qwen2.5-coder:7b)"
curl -fsS "http://${GATEWAY}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-portkey-api-key: ${KEY}" \
  -H "x-portkey-config: ${CONFIG}" \
  -d '{
    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    "max_tokens": 16
  }' | head -c 600
echo

echo "==> Smoke coding task"
curl -fsS "http://${GATEWAY}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-portkey-api-key: ${KEY}" \
  -H "x-portkey-config: ${CONFIG}" \
  -d '{
    "messages": [{"role": "user", "content": "Write a Python function that calculates the factorial of a number. Include a docstring and type hints."}],
    "max_tokens": 200
  }' | head -c 800
echo

echo "Smoke test complete."