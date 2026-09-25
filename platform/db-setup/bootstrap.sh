#!/bin/bash
set -e

# psql needs the password in the environment; the superuser password is already
# injected by Compose as POSTGRES_DB_PASSWORD (PGPASSWORD is left empty by the
# compose file), so export it explicitly.
export PGPASSWORD="${POSTGRES_DB_PASSWORD}"

PSQL="psql -v ON_ERROR_STOP=1 -a -h ${POSTGRES_HOST} -U ${POSTGRES_DB_USER} -d postgres"

echo "Applying Database creation..."
envsubst < /db-setup/001_create_databases.sql | grep -v "(''')" | $PSQL

echo "Applying User creation..."
envsubst < /db-setup/002_create_users.sql | $PSQL

echo "Applying Permissions..."
envsubst < /db-setup/003_apply_permissions.sql | $PSQL

echo "Bootstrap complete."