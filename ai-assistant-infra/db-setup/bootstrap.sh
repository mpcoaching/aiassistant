#!/bin/bash
set -e

PSQL="psql -v ON_ERROR_STOP=1 -a -e -h ${POSTGRES_HOST} -U ${POSTGRES_DB_USER} -d postgres"

echo "Applying Database creation..."
$PSQL -f /db-setup/001_create_databases.sql

echo "Applying User creation..."
$PSQL -f /db-setup/002_create_users.sql

echo "Applying Permissions..."
$PSQL -f /db-setup/003_apply_permissions.sql

echo "Bootstrap complete."
