-- 001_create_databases.sql
-- Tenant-readiness: name convention is <tenant>_<env>. Today the tenant is the
-- platform default ("agent"). A future tenant_a_live is added here + in 002/003.
--
-- Values are read straight from the container environment with psql's \getenv
-- instead of an envsubst pre-pass. The old envsubst approach needed gettext in
-- the image; the bootstrapper image did not have it, so this file never actually
-- ran and the databases it creates were silently missing on a pre-seeded volume.
--
-- %I quotes identifiers, so names containing unusual characters are safe.
\getenv agent_dev_db      AGENT_DEV_DB_NAME
\getenv agent_live_db     AGENT_LIVE_DB_NAME
\getenv n8n_db            N8N_DB_NAME
\getenv langgraph_db      LANGGRAPH_DB_NAME
\getenv langgraph_dev_db  LANGGRAPH_DEV_DB_NAME
\getenv langgraph_live_db LANGGRAPH_LIVE_DB_NAME
\getenv langfuse_db       LANGFUSE_DB_NAME
\getenv openobserve_db    OPENOBSERVE_DB_NAME
\getenv clickhouse_db     CLICKHOUSE_DB_NAME

SELECT format('CREATE DATABASE %I', db) AS stmt
FROM (VALUES
    (:'agent_dev_db'),
    (:'agent_live_db'),
    (:'n8n_db'),
    (:'langgraph_db'),
    (:'langgraph_dev_db'),
    (:'langgraph_live_db'),
    (:'langfuse_db'),
    (:'openobserve_db'),
    (:'clickhouse_db')
) AS wanted(db)
WHERE db <> ''
  AND NOT EXISTS (SELECT FROM pg_database WHERE datname = db)
\gexec
