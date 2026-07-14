#!/bin/bash
set -e

PSQL="psql -v ON_ERROR_STOP=1 -a -e -h ${POSTGRES_HOST} -U ${POSTGRES_DB_USER} -d postgres"

echo "Applying Database creation..."
envsubst < /db-setup/001_create_databases.sql | $PSQL

echo "Applying User creation..."
envsubst < /db-setup/002_create_users.sql | $PSQL

echo "Applying Permissions..."
envsubst < /db-setup/003_apply_permissions.sql | $PSQL

echo "Bootstrap complete."
