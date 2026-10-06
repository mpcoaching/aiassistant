#!/bin/sh
# Platform database bootstrap.
#
# Runs on every `docker compose up` of the platform because db-bootstrapper is a
# dependency of migrate-dev/migrate-live/langfuse. It must therefore be safe to
# run repeatedly against an already-initialised volume, and it must never be a
# silent no-op: an earlier version skipped itself when psql was missing, which
# let the platform come up with roles/databases missing and left migrate-*
# crash-looping on "password authentication failed".
#
# The image is postgres:16-alpine, which ships psql. Values are read from the
# environment by the SQL files themselves via psql \getenv, so no envsubst/gettext
# dependency is required.
set -eu

# psql reads the superuser password from the environment. Compose deliberately
# leaves PGPASSWORD empty, so export it from the injected variable.
PGPASSWORD="${POSTGRES_DB_PASSWORD}"
export PGPASSWORD

psql_super() {
    psql -v ON_ERROR_STOP=1 -q -h "${POSTGRES_HOST}" -U "${POSTGRES_DB_USER}" -d postgres
}

echo "Applying database creation..."
psql_super < /db-setup/001_create_databases.sql

echo "Applying user creation..."
psql_super < /db-setup/002_create_users.sql

echo "Applying permissions..."
psql_super < /db-setup/003_apply_permissions.sql

# Schema-level grants must be applied inside each application database, so this
# reconnects per pair instead of relying on \gexec (which stays in `postgres`).
# 003_apply_permissions.sql documents why.
echo "Applying per-database schema grants..."
for pair in \
    "${AGENT_DEV_DB_NAME}:${AGENT_DEV_DB_USER}" \
    "${AGENT_LIVE_DB_NAME}:${AGENT_LIVE_DB_USER}" \
    "${N8N_DB_NAME}:${N8N_DB_USER}" \
    "${LANGGRAPH_DB_NAME}:${LANGGRAPH_DB_USER}" \
    "${LANGGRAPH_DEV_DB_NAME}:${LANGGRAPH_DEV_DB_USER}" \
    "${LANGGRAPH_LIVE_DB_NAME}:${LANGGRAPH_LIVE_DB_USER}" \
    "${LANGFUSE_DB_NAME}:${LANGFUSE_DB_USER}" \
    "${OPENOBSERVE_DB_NAME}:${OPENOBSERVE_DB_USER}" \
    "${CLICKHOUSE_DB_NAME}:${CLICKHOUSE_DB_USER}"
do
    db=${pair%%:*}
    usr=${pair##*:}
    [ -n "$db" ] && [ -n "$usr" ] || continue

    # Skip databases this platform does not actually host (e.g. clickhouse keeps
    # its own user store, and a name may be unset on a given host).
    if ! psql -v ON_ERROR_STOP=1 -qtA -h "${POSTGRES_HOST}" -U "${POSTGRES_DB_USER}" \
         -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1
    then
        echo "  skip $db (not present in this Postgres)"
        continue
    fi

    echo "  $db <- $usr"
    psql -v ON_ERROR_STOP=1 -q -h "${POSTGRES_HOST}" -U "${POSTGRES_DB_USER}" -d "$db" \
        -v db="$db" -v usr="$usr" <<'SQL'
GRANT ALL ON SCHEMA public TO :"usr";
ALTER SCHEMA public OWNER TO :"usr";
GRANT ALL ON ALL TABLES IN SCHEMA public TO :"usr";
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO :"usr";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO :"usr";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO :"usr";
SQL
done

echo "Bootstrap complete."
