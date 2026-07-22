-- 002_create_users.sql
-- Per-env roles enforce isolation: agent_dev_user owns ONLY agent_dev,
-- agent_live_user owns ONLY agent_live. No cross-env access is possible.
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
