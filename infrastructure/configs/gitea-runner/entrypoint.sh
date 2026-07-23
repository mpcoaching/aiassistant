#!/bin/bash
set -euo pipefail

RUNNER_STATE="${RUNNER_STATE:-/data/.runner}"
CONFIG="${CONFIG:-/data/config.yml}"
CONFIG_TEMPLATE="${CONFIG_TEMPLATE:-/data/config.template.yaml}"
LOG_TAG="[gitea-runner]"

generate_config() {
    echo "$LOG_TAG Generating config.yml from template..."
    cp "${CONFIG_TEMPLATE}" "${CONFIG}"
    for var in GITEA_INSTANCE_URL GITEA_RUNNER_REGISTRATION_TOKEN GITEA_RUNNER_NAME GITEA_RUNNER_LABELS; do
        val="${!var:-}"
        escaped_val=$(printf '%s\n' "$val" | sed 's/[&/\]/\\&/g')
        sed -i "s|\${${var}}|${escaped_val}|g" "${CONFIG}"
    done
}

register_runner() {
    local max_attempts=3
    local attempt=1
    local wait=5

    echo "$LOG_TAG No .runner found, registering with Gitea..."

    until curl -fsS "${GITEA_INSTANCE_URL}/api/v1/version" >/dev/null 2>&1; do
        echo "$LOG_TAG Waiting for Gitea at ${GITEA_INSTANCE_URL}..."
        sleep 3
    done

    while [ $attempt -le $max_attempts ]; do
        echo "$LOG_TAG Registration attempt $attempt/$max_attempts..."
        if act_runner register \
            --instance "${GITEA_INSTANCE_URL}" \
            --token "${GITEA_RUNNER_REGISTRATION_TOKEN}" \
            --name "${GITEA_RUNNER_NAME}" \
            --labels "${GITEA_RUNNER_LABELS}" \
            --config "${CONFIG}"; then
            echo "$LOG_TAG Registration complete"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep $wait
        wait=$((wait * 2))
    done

    echo "$LOG_TAG Registration failed after $max_attempts attempts"
    return 1
}

start_daemon() {
    echo "$LOG_TAG Starting daemon..."
    exec act_runner daemon --config "${CONFIG}"
}

gitea_runner_lifecycle() {
    if [ ! -f "${CONFIG}" ] && [ -f "${CONFIG_TEMPLATE}" ]; then
        generate_config
    fi

    if [ ! -f "${RUNNER_STATE}" ]; then
        if ! register_runner; then
            echo "$LOG_TAG Fatal: could not register runner with Gitea" >&2
            exit 1
        fi
    fi

    start_daemon
}

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    gitea_runner_lifecycle
fi
