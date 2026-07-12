-- 003_apply_permissions.sql
WITH dbs_users(db_name, user_name) AS (
    VALUES ('${AIASSIST_DB_NAME}', '${AIASSIST_DB_USER}'),
           ('${AIASSIST_DEV_DB_NAME}', '${AIASSIST_DB_USER}'),
           ('${AIASSIST_LIVE_DB_NAME}', '${AIASSIST_DB_USER}'),
           ('${N8N_DB_NAME}', '${N8N_DB_USER}'),
           ('${LANGGRAPH_DB_NAME}', '${LANGGRAPH_DB_USER}'),
           ('${LANGGRAPH_DEV_DB_NAME}', '${LANGGRAPH_DB_USER}'),
           ('${LANGGRAPH_LIVE_DB_NAME}', '${LANGGRAPH_DB_USER}'),
           ('${LANGFUSE_DB_NAME}', '${LANGFUSE_DB_USER}'),
           ('${OPENOBSERVE_DB_NAME}', '${OPENOBSERVE_DB_USER}'),
           ('${LITELLM_DB_NAME}', '${LITELLM_DB_USER}'),
           ('${LITELLM_DEV_DB_NAME}', '${LITELLM_DB_USER}'),
           ('${LITELLM_LIVE_DB_NAME}', '${LITELLM_DB_USER}'),
           ('${CLICKHOUSE_DB_NAME}', '${CLICKHOUSE_DB_USER}'),
		   ('${OPENHANDS_DB_NAME}', '${OPENHANDS_DB_USER}'),
		   ('${TEAMCITY_DB_NAME}', '${TEAMCITY_DB_USER}')
)
SELECT 
    'REVOKE ALL ON DATABASE "' || db_name || '" FROM PUBLIC;' ||
    'GRANT CONNECT ON DATABASE "' || db_name || '" TO "' || user_name || '";' ||
    'ALTER DATABASE "' || db_name || '" OWNER TO "' || user_name || '";' ||
    'ALTER SCHEMA public OWNER TO "' || user_name || '";'
FROM dbs_users
\gexec