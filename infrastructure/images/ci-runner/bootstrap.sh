#!/bin/sh
# bootstrap entrypoint for CI Worker

set -e

CONFIG_MANAGER_URL="${CONFIG_MANAGER_URL:?CONFIG_MANAGER_URL not set}"
CAPABILITY="${CAPABILITY:?CAPABILITY not set}"

echo "Requesting validated contract for ${CAPABILITY} from Configuration Manager..."

RESPONSE=$(curl -sf "${CONFIG_MANAGER_URL}/contracts/${CAPABILITY}")

STATUS=$(echo "$RESPONSE" | jq -r '.status')
if [ "$STATUS" != "validated" ]; then
  echo "Contract validation failed for ${CAPABILITY}"
  echo "$RESPONSE" | jq '.errors // .detail // .'
  exit 1
fi

export GITEA_URL="$(echo "$RESPONSE" | jq -r '.configuration.GITEA_URL')"
export RUNNER_TOKEN="$(echo "$RESPONSE" | jq -r '.configuration.RUNNER_TOKEN')"

echo "Contract validated for ${CAPABILITY}, starting runner..."

exec runner start