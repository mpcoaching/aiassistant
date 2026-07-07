#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status

# Define the psql command
# -v ON_ERROR_STOP=1: Stop on ANY error
# -a: Echo all input queries (great for debugging)
# -e: Echo errors
PSQL="psql -v ON_ERROR_STOP=1 -a -e -h ${POSTGRES_HOST} -U ${POSTGRES_USER} -d postgres"

echo "Applying Database creation..."
$PSQL -f /migrations/001_create_databases.sql

echo "Applying User creation..."
$PSQL -f /migrations/002_create_users.sql

echo "Applying Permissions..."
$PSQL -f /migrations/003_apply_permissions.sql

echo "Bootstrap complete."