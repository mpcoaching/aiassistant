-- 003_apply_permissions.sql
-- GRANTs + ownership are scoped per (db, user) pair. The dev user cannot touch
-- the live DB and vice-versa — this is the DB-level isolation boundary.
--
-- This file handles DATABASE-level privileges only. Schema-level grants inside
-- each application database (GRANT ... ON SCHEMA public, ALTER SCHEMA public
-- OWNER) cannot live here: \gexec runs every generated statement in the current
-- database, which is `postgres`, so an ALTER SCHEMA public in this file would
-- silently retarget the postgres database's schema instead of the application's.
-- Those statements are applied per database by bootstrap.sh, which reconnects to
-- each target database in turn.
\getenv agent_dev_db      AGENT_DEV_DB_NAME
\getenv agent_dev_user    AGENT_DEV_DB_USER
\getenv agent_live_db     AGENT_LIVE_DB_NAME
\getenv agent_live_user   AGENT_LIVE_DB_USER
\getenv n8n_db            N8N_DB_NAME
\getenv n8n_user          N8N_DB_USER
\getenv langgraph_db      LANGGRAPH_DB_NAME
\getenv langgraph_user    LANGGRAPH_DB_USER
\getenv langgraph_dev_db  LANGGRAPH_DEV_DB_NAME
\getenv langgraph_dev_user LANGGRAPH_DEV_DB_USER
\getenv langgraph_live_db LANGGRAPH_LIVE_DB_NAME
\getenv langgraph_live_user LANGGRAPH_LIVE_DB_USER
\getenv langfuse_db       LANGFUSE_DB_NAME
\getenv langfuse_user     LANGFUSE_DB_USER
\getenv openobserve_db    OPENOBSERVE_DB_NAME
\getenv openobserve_user  OPENOBSERVE_DB_USER
\getenv clickhouse_db     CLICKHOUSE_DB_NAME
\getenv clickhouse_user   CLICKHOUSE_DB_USER

SELECT
    format('REVOKE ALL ON DATABASE %I FROM PUBLIC;', db) ||
    format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I;', db, usr) ||
    format('ALTER DATABASE %I OWNER TO %I;', db, usr) AS stmt
FROM (VALUES
    (:'agent_dev_db',      :'agent_dev_user'),
    (:'agent_live_db',     :'agent_live_user'),
    (:'n8n_db',            :'n8n_user'),
    (:'langgraph_db',      :'langgraph_user'),
    (:'langgraph_dev_db',  :'langgraph_dev_user'),
    (:'langgraph_live_db', :'langgraph_live_user'),
    (:'langfuse_db',       :'langfuse_user'),
    (:'openobserve_db',    :'openobserve_user'),
    (:'clickhouse_db',     :'clickhouse_user')
) AS wanted(db, usr)
WHERE db <> '' AND usr <> ''
\gexec
