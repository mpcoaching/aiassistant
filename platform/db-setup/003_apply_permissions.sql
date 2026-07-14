-- 003_apply_permissions.sql
-- GRANTs + ownership are scoped per (db, user) pair. The dev user cannot touch
-- the live DB and vice-versa — this is the DB-level isolation boundary.
WITH dbs_users(db_name, user_name) AS (
    VALUES ('${AGENT_DEV_DB_NAME}',    '${AGENT_DEV_DB_USER}'),
           ('${AGENT_LIVE_DB_NAME}',   '${AGENT_LIVE_DB_USER}'),
           ('${N8N_DB_NAME}',          '${N8N_DB_USER}'),
           ('${LANGGRAPH_DB_NAME}',    '${LANGGRAPH_DB_USER}'),
           ('${LANGGRAPH_DEV_DB_NAME}',    '${LANGGRAPH_DEV_DB_USER}'),
           ('${LANGGRAPH_LIVE_DB_NAME}',   '${LANGGRAPH_LIVE_DB_USER}'),
           ('${LANGFUSE_DB_NAME}',     '${LANGFUSE_DB_USER}'),
           ('${OPENOBSERVE_DB_NAME}',  '${OPENOBSERVE_DB_USER}'),
           ('${LITELLM_DB_NAME}',      '${LITELLM_DB_USER}'),
           ('${CLICKHOUSE_DB_NAME}',   '${CLICKHOUSE_DB_USER}'),
           ('${TEAMCITY_DB_NAME}',     '${TEAMCITY_DB_USER}'),
           ('${MANIFEST_DB_NAME}',     '${MANIFEST_DB_USER}')
)
SELECT
    'REVOKE ALL ON DATABASE "' || db_name || '" FROM PUBLIC;' ||
    'GRANT CONNECT ON DATABASE "' || db_name || '" TO "' || user_name || '";' ||
    'ALTER DATABASE "' || db_name || '" OWNER TO "' || user_name || '";' ||
    'ALTER SCHEMA public OWNER TO "' || user_name || '";'
FROM dbs_users
\gexec
