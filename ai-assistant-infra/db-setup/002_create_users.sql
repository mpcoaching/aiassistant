-- 002_create_users.sql
SELECT 'CREATE USER "' || user_name || '" WITH ENCRYPTED PASSWORD ''' || pass || ''';'
FROM (VALUES 
    ('${AIASSIST_DB_USER}', '${AIASSIST_DB_PASSWORD}'),
    ('${N8N_DB_USER}', '${N8N_DB_PASSWORD}'),
    ('${LANGGRAPH_DB_USER}', '${LANGGRAPH_DB_PASSWORD}'),
    ('${LANGFUSE_DB_USER}', '${LANGFUSE_DB_PASSWORD}'),
    ('${OPENOBSERVE_DB_USER}', '${OPENOBSERVE_DB_PASSWORD}'),
    ('${LITELLM_DB_USER}', '${LITELLM_DB_PASSWORD}'),
    ('${CLICKHOUSE_DB_USER}', '${CLICKHOUSE_DB_PASSWORD}'),
	('${OPENHANDS_DB_USER}', '${OPENHANDS_DB_PASSWORD}'),
	('${TEAMCITY_DB_USER}', '${TEAMCITY_DB_PASSWORD}')
) AS users(user_name, pass)
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = user_name)
\gexec