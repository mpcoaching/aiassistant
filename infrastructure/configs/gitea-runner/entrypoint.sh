#!/bin/bash
set -euo pipefail

RUNNER_STATE="/data/.runner"
CONFIG="/data/config.yml"
CONFIG_TEMPLATE="/data/config.template.yaml"

# Gitea act_runner lifecycle:
# 1. Generate config.yml from config.template.yaml using envsubst so that
#    environment variables (GITEA_INSTANCE_URL, registration token, etc.)
#    are resolved at runtime. Compose does not substitute into read-only
#    volume mounts, so this step is mandatory.
# 2. If /data/.runner is missing, run `register` with the current token.
# 3. Run `daemon` which polls Gitea for jobs using the stored registration.
#
# The .runner file contains the runner UUID + token. Deleting it forces
# re-registration on next start. Do not delete it manually during normal
# operation — it is the runner's persistent identity in Gitea's database.

if [ ! -f "${CONFIG}" ] || [ -f "${CONFIG_TEMPLATE}" ]; then
    echo "[gitea-runner] Generating config.yml from template..."
    cp "${CONFIG_TEMPLATE}" "${CONFIG}"
    for var in GITEA_INSTANCE_URL GITEA_RUNNER_REGISTRATION_TOKEN GITEA_RUNNER_NAME GITEA_RUNNER_LABELS; do
        val="${!var}"
        sed -i "s|\${${var}}|${val}|g" "${CONFIG}"
    done
fi

if [ ! -f "${RUNNER_STATE}" ]; then
    echo "[gitea-runner] No .runner found, registering with Gitea..."
    
    until curl -fsS "${GITEA_INSTANCE_URL}/api/v1/version" >/dev/null 2>&1; do
        echo "[gitea-runner] Waiting for Gitea at ${GITEA_INSTANCE_URL}..."
        sleep 3
    done
    
    act_runner register \
        --instance "${GITEA_INSTANCE_URL}" \
        --token "${GITEA_RUNNER_REGISTRATION_TOKEN}" \
        --name "${GITEA_RUNNER_NAME}" \
        --labels "${GITEA_RUNNER_LABELS}" \
        --config "${CONFIG}"
    
    echo "[gitea-runner] Registration complete"
fi

echo "[gitea-runner] Starting daemon..."
exec act_runner daemon --config "${CONFIG}"
