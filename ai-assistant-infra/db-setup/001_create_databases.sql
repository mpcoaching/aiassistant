-- 001_create_databases.sql
WITH dbs(name) AS (
    VALUES ('${AIASSIST_DB_NAME}'),
           ('${N8N_DB_NAME}'),
           ('${LANGGRAPH_DB_NAME}'),
           ('${LANGFUSE_DB_NAME}'),
           ('${OPENOBSERVE_DB_NAME}'),
           ('${LITELLM_DB_NAME}'),
           ('${CLICKHOUSE_DB_NAME}'),
		   ('${OPENHANDS_DB_NAME}')
)
SELECT 'CREATE DATABASE "' || name || '"'
FROM dbs
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = name)
\gexec