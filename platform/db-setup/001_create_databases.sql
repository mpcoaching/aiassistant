-- 001_create_databases.sql
-- Tenant-readiness: name convention is <tenant>_<env>. Today the tenant is the
-- platform default ("agent"). A future tenant_a_live is added here + in 002/003.
WITH dbs(name) AS (
    VALUES ('${AGENT_DEV_DB_NAME}'),
           ('${AGENT_LIVE_DB_NAME}'),
           ('${N8N_DB_NAME}'),
           ('${LANGGRAPH_DB_NAME}'),
           ('${LANGGRAPH_DEV_DB_NAME}'),
           ('${LANGGRAPH_LIVE_DB_NAME}'),
           ('${LANGFUSE_DB_NAME}'),
           ('${OPENOBSERVE_DB_NAME}'),
           ('${LITELLM_DB_NAME}'),
           ('${CLICKHOUSE_DB_NAME}'),
           ('${OPENHANDS_DB_NAME}'),
           ('${TEAMCITY_DB_NAME}'),
           ('${MANIFEST_DB_NAME}'),
           ('${OPENCODE_DB_NAME}')
)
SELECT 'CREATE DATABASE "' || name || '"'
FROM dbs
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = name)
\gexec
