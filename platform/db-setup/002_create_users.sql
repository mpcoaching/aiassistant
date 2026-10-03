-- 002_create_users.sql
-- Per-env roles enforce isolation: agent_dev_user owns ONLY agent_dev,
-- agent_live_user owns ONLY agent_live. No cross-env access is possible.
--
-- Two statements per role, both idempotent:
--   CREATE USER  -- only when the role does not exist yet
--   ALTER  ...   -- ALWAYS, to converge an existing role's password onto the
--                   value in the current .env
--
-- The ALTER is not cosmetic. Roles are created once, when the Postgres volume
-- is first seeded, and PostgreSQL never re-reads their password afterwards.
-- A `CREATE ... WHERE NOT EXISTS`-only script therefore silently freezes the
-- password from that first run: any later .env edit diverges from the live
-- database, and services start reporting
--   "password authentication failed for user <role>"
-- even though .env looks correct. Setting the password on every run makes the
-- committed .env.template the single source of truth and removes that drift.
--
-- Passwords come from the environment via envsubst (see bootstrap.sh).
SELECT 'CREATE USER "' || user_name || '" WITH ENCRYPTED PASSWORD ''' || pass || ''';'
FROM (VALUES
    ('${AGENT_DEV_DB_USER}',   '${AGENT_DEV_DB_PASSWORD}'),
    ('${AGENT_LIVE_DB_USER}',  '${AGENT_LIVE_DB_PASSWORD}'),
    ('${N8N_DB_USER}',         '${N8N_DB_PASSWORD}'),
    ('${LANGGRAPH_DB_USER}',   '${LANGGRAPH_DB_PASSWORD}'),
    ('${LANGGRAPH_DEV_DB_USER}',   '${LANGGRAPH_DEV_DB_PASSWORD}'),
    ('${LANGGRAPH_LIVE_DB_USER}',  '${LANGGRAPH_LIVE_DB_PASSWORD}'),
    ('${LANGFUSE_DB_USER}',    '${LANGFUSE_DB_PASSWORD}'),
    ('${OPENOBSERVE_DB_USER}', '${OPENOBSERVE_DB_PASSWORD}'),
    ('${CLICKHOUSE_DB_USER}',  '${CLICKHOUSE_DB_PASSWORD}')
) AS users(user_name, pass)
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = user_name)
\gexec

-- Converge passwords for roles that already exist. ALTER ROLE also works on a
-- role that does not exist yet in older setups, but every role above is
-- created by the block above on a fresh volume, so this always finds its
-- target.
SELECT 'ALTER ROLE "' || user_name || '" WITH LOGIN PASSWORD ''' || pass || ''';'
FROM (VALUES
    ('${AGENT_DEV_DB_USER}',   '${AGENT_DEV_DB_PASSWORD}'),
    ('${AGENT_LIVE_DB_USER}',  '${AGENT_LIVE_DB_PASSWORD}'),
    ('${N8N_DB_USER}',         '${N8N_DB_PASSWORD}'),
    ('${LANGGRAPH_DB_USER}',   '${LANGGRAPH_DB_PASSWORD}'),
    ('${LANGGRAPH_DEV_DB_USER}',   '${LANGGRAPH_DEV_DB_PASSWORD}'),
    ('${LANGGRAPH_LIVE_DB_USER}',  '${LANGGRAPH_LIVE_DB_PASSWORD}'),
    ('${LANGFUSE_DB_USER}',    '${LANGFUSE_DB_PASSWORD}'),
    ('${OPENOBSERVE_DB_USER}', '${OPENOBSERVE_DB_PASSWORD}'),
    ('${CLICKHOUSE_DB_USER}',  '${CLICKHOUSE_DB_PASSWORD}')
) AS users(user_name, pass)
WHERE EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = user_name)
\gexec
