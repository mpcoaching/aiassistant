#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTRYPOINT="$SCRIPT_DIR/entrypoint.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; exit 1; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
write_template() {
    cat > "$TMPDIR/template.yaml" <<'YAML'
instance: ${GITEA_INSTANCE_URL}
runner: ${GITEA_RUNNER_NAME}
token: ${GITEA_RUNNER_REGISTRATION_TOKEN}
labels: ${GITEA_RUNNER_LABELS}
YAML
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
test_generate_config_substitutes_all_vars() {
    write_template
    export GITEA_INSTANCE_URL="http://gitea:3000"
    export GITEA_RUNNER_NAME="test-runner"
    export GITEA_RUNNER_REGISTRATION_TOKEN="secret-token"
    export GITEA_RUNNER_LABELS="ubuntu-latest"
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"
    generate_config

    grep -q "http://gitea:3000" "$TMPDIR/config.yml" || fail "INSTANCE_URL not substituted"
    grep -q "test-runner" "$TMPDIR/config.yml" || fail "RUNNER_NAME not substituted"
    grep -q "secret-token" "$TMPDIR/config.yml" || fail "TOKEN not substituted"
    grep -q "ubuntu-latest" "$TMPDIR/config.yml" || fail "LABELS not substituted"
    pass "generate_config substitutes all vars"
}

test_generate_config_empty_env_leaves_empty() {
    write_template
    export GITEA_INSTANCE_URL=""
    export GITEA_RUNNER_NAME=""
    export GITEA_RUNNER_REGISTRATION_TOKEN=""
    export GITEA_RUNNER_LABELS=""
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"
    generate_config

    grep -q "instance: $" "$TMPDIR/config.yml" || fail "empty INSTANCE_URL"
    grep -q "runner: $" "$TMPDIR/config.yml" || fail "empty RUNNER_NAME"
    pass "generate_config handles empty env vars"
}

test_generate_config_escapes_sed_special_chars() {
    write_template
    export GITEA_INSTANCE_URL="http://gitea:3000/some&path"
    export GITEA_RUNNER_NAME="test/runner"
    export GITEA_RUNNER_REGISTRATION_TOKEN="tok&en"
    export GITEA_RUNNER_LABELS="ubuntu-latest"
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"
    generate_config

    grep -q "some&path" "$TMPDIR/config.yml" || fail "ampersand in URL not preserved"
    grep -q "test/runner" "$TMPDIR/config.yml" || fail "slash in name not preserved"
    grep -q "tok&en" "$TMPDIR/config.yml" || fail "ampersand in token not preserved"
    pass "generate_config escapes sed special characters"
}

test_runner_skips_registration_when_runner_exists() {
    write_template
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"
    export RUNNER_STATE="$TMPDIR/.runner"
    export GITEA_INSTANCE_URL="http://gitea:3000"
    export GITEA_RUNNER_NAME="test"
    export GITEA_RUNNER_REGISTRATION_TOKEN="tok"
    export GITEA_RUNNER_LABELS="label"
    export LOG_TAG="[gitea-runner]"

    generate_config
    touch "$RUNNER_STATE"

    register_called=0
    daemon_called=0

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"

    start_daemon() { daemon_called=1; }
    act_runner() { [ "${1:-}" = "register" ] && register_called=$((register_called + 1)); }
    curl() { return 0; }

    gitea_runner_lifecycle || true

    [ "$register_called" -eq 0 ] || fail "register was called when .runner exists"
    [ "$daemon_called" -eq 1 ] || fail "daemon was not started when .runner exists"
    pass "registration skipped when .runner exists"
}

test_runner_retries_registration_on_failure() {
    write_template
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"
    export RUNNER_STATE="$TMPDIR/.runner_placeholder"
    export GITEA_INSTANCE_URL="http://gitea:3000"
    export GITEA_RUNNER_NAME="test"
    export GITEA_RUNNER_REGISTRATION_TOKEN="tok"
    export GITEA_RUNNER_LABELS="label"
    export LOG_TAG="[gitea-runner]"

    register_attempts=0
    daemon_called=0

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"

    start_daemon() { daemon_called=1; }
    act_runner() {
        [ "${1:-}" = "register" ] && register_attempts=$((register_attempts + 1))
        return 1
    }
    curl() { return 0; }

    gitea_runner_lifecycle || true

    [ "$register_attempts" -eq 3 ] || fail "expected 3 register attempts, got $register_attempts"
    [ "$daemon_called" -eq 0 ] || fail "daemon should not start after failed registration"
    pass "registration retries 3 times and exits on failure"
}

test_runner_skips_config_regeneration_when_config_exists() {
    write_template
    export CONFIG_TEMPLATE="$TMPDIR/template.yaml"
    export CONFIG="$TMPDIR/config.yml"
    export RUNNER_STATE="$TMPDIR/.runner"
    export GITEA_INSTANCE_URL="http://gitea:3000"
    export GITEA_RUNNER_NAME="test"
    export GITEA_RUNNER_REGISTRATION_TOKEN="tok"
    export GITEA_RUNNER_LABELS="label"
    export LOG_TAG="[gitea-runner]"

    generate_config
    touch "$RUNNER_STATE"
    original_content=$(cat "$TMPDIR/config.yml")

    daemon_called=0

    # shellcheck disable=SC1090
    source "$ENTRYPOINT"

    start_daemon() { daemon_called=1; }
    act_runner() { :; }
    curl() { return 0; }

    gitea_runner_lifecycle || true

    [ "$(cat "$TMPDIR/config.yml")" = "$original_content" ] || fail "config was overwritten when it shouldn't be"
    [ "$daemon_called" -eq 1 ] || fail "daemon was not started when config and .runner exist"
    pass "config not regenerated when already present"
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
test_generate_config_substitutes_all_vars
test_generate_config_empty_env_leaves_empty
test_generate_config_escapes_sed_special_chars
test_runner_skips_registration_when_runner_exists
test_runner_retries_registration_on_failure
test_runner_skips_config_regeneration_when_config_exists

echo ""
echo "All tests passed."
