-- 002_create_users.sql
-- Per-env roles enforce isolation: agent_dev_user owns ONLY agent_dev,
-- agent_live_user owns ONLY agent_live. No cross-env access is possible.
--
-- Two statements per role, both idempotent:
--   CREATE USER  -- only when the role does not exist yet
--   ALTER  ...   -- ALWAYS, to converge an existing role's password onto the
--                   value in the current environment
--
-- The ALTER is not cosmetic. Roles are created once, when the Postgres volume
-- is first seeded, and PostgreSQL never re-reads their password afterwards.
-- A `CREATE ... WHERE NOT EXISTS`-only script therefore silently freezes the
-- password from that first run: any later env edit diverges from the live
-- database, and services start reporting
--   "password authentication failed for user <role>"
-- even though the env file looks correct. Setting the password on every run makes
-- the environment the single source of truth and removes that drift.
--
-- Values come from the container environment via psql \getenv (see bootstrap.sh).
-- %I quotes the role name and %L quotes the password literal, so a password
-- containing a quote can no longer break the generated statement.
\getenv agent_dev_user       AGENT_DEV_DB_USER
\getenv agent_dev_pass       AGENT_DEV_DB_PASSWORD
\getenv agent_live_user      AGENT_LIVE_DB_USER
\getenv agent_live_pass      AGENT_LIVE_DB_PASSWORD
\getenv n8n_user             N8N_DB_USER
\getenv n8n_pass             N8N_DB_PASSWORD
\getenv langgraph_user       LANGGRAPH_DB_USER
\getenv langgraph_pass       LANGGRAPH_DB_PASSWORD
\getenv langgraph_dev_user   LANGGRAPH_DEV_DB_USER
\getenv langgraph_dev_pass   LANGGRAPH_DEV_DB_PASSWORD
\getenv langgraph_live_user  LANGGRAPH_LIVE_DB_USER
\getenv langgraph_live_pass  LANGGRAPH_LIVE_DB_PASSWORD
\getenv langfuse_user        LANGFUSE_DB_USER
\getenv langfuse_pass        LANGFUSE_DB_PASSWORD
\getenv openobserve_user     OPENOBSERVE_DB_USER
\getenv openobserve_pass     OPENOBSERVE_DB_PASSWORD
\getenv clickhouse_user      CLICKHOUSE_DB_USER
\getenv clickhouse_pass      CLICKHOUSE_DB_PASSWORD

SELECT format('CREATE USER %I WITH ENCRYPTED PASSWORD %L', usr, pwd) AS stmt
FROM (VALUES
    (:'agent_dev_user',      :'agent_dev_pass'),
    (:'agent_live_user',     :'agent_live_pass'),
    (:'n8n_user',            :'n8n_pass'),
    (:'langgraph_user',      :'langgraph_pass'),
    (:'langgraph_dev_user',  :'langgraph_dev_pass'),
    (:'langgraph_live_user', :'langgraph_live_pass'),
    (:'langfuse_user',       :'langfuse_pass'),
    (:'openobserve_user',    :'openobserve_pass'),
    (:'clickhouse_user',     :'clickhouse_pass')
) AS wanted(usr, pwd)
WHERE usr <> ''
  AND NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = usr)
\gexec

-- Converge passwords for roles that already exist. Every role above is created
-- by the block above on a fresh volume, so this always finds its target.
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', usr, pwd) AS stmt
FROM (VALUES
    (:'agent_dev_user',      :'agent_dev_pass'),
    (:'agent_live_user',     :'agent_live_pass'),
    (:'n8n_user',            :'n8n_pass'),
    (:'langgraph_user',      :'langgraph_pass'),
    (:'langgraph_dev_user',  :'langgraph_dev_pass'),
    (:'langgraph_live_user', :'langgraph_live_pass'),
    (:'langfuse_user',       :'langfuse_pass'),
    (:'openobserve_user',    :'openobserve_pass'),
    (:'clickhouse_user',     :'clickhouse_pass')
) AS wanted(usr, pwd)
WHERE usr <> ''
  AND EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = usr)
\gexec
