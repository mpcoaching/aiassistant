# Two-Stack Infra + Agentic Split — Corrected Plan

## Context Update

User confirmed: **two Docker stacks** — `docker-compose.platform.yml` (true infra substrate shared by all tiers) and `docker-compose.yml` (the agentic implementation stack that *consumes* that infra). Kilo owns the platform repo/config and a TeamCity worker deploys via docker compose on the server.

## Corrections Required

1. **Do not extend `db-setup/*.sql`** to add per-env users.
2. **Do not add new numbered SQL files** under `ai-assistant-infra/db-setup/`.
3. Use the **db-bootstrapper service** (not the SQL files it mounts) to create per-env DB users from `.env` vars, OR use the **migrate container** (goose) for schema/bootstrap.
4. Add **per-env DB vars** (both names AND users) to `.env` / `.env.template`.

## Affected Boundaries

- `docker-compose.platform.yml` — `db-bootstrapper` and `migrate` service definitions + env wiring.
- `docker-compose.yml` — agentic `workflow-engine`, `langgraph`, `litellm` connection strings must each target their **own env-specific DB and DB user**.
- `.env.template` — every per-env DB needs a matching per-env DB user var.
- `ai-assistant-infra/db-setup/` — keep as-is; do not extend.

## Task List

### 1. Add per-env DB users / names to `.env.template`

Add the following vars (group under existing Dev/Live per-env section):

```
# ===== Per-env DB names =====
AIASSIST_DEV_DB_NAME=aiassistant_dev
AIASSIST_LIVE_DB_NAME=aiassistant_live
LANGGRAPH_DEV_DB_NAME=langgraph_dev
LANGGRAPH_LIVE_DB_NAME=langgraph_live
LITELLM_DEV_DB_NAME=litellm_dev
LITELLM_LIVE_DB_NAME=litellm_live

# ===== Per-env DB users =====
AIASSIST_DEV_DB_USER=aiassistant_dev_user
AIASSIST_DEV_DB_PASSWORD=dev_user_password
AIASSIST_LIVE_DB_USER=aiassistant_live_user
AIASSIST_LIVE_DB_PASSWORD=live_user_password
LANGGRAPH_DEV_DB_USER=langgraph_dev_user
LANGGRAPH_DEV_DB_PASSWORD=dev_langgraph_password
LANGGRAPH_LIVE_DB_USER=langgraph_live_user
LANGGRAPH_LIVE_DB_PASSWORD=live_langgraph_password
LITELLM_DEV_DB_USER=litellm_dev_user
LITELLM_DEV_DB_PASSWORD=dev_litellm_password
LITELLM_LIVE_DB_USER=litellm_live_user
LITELLM_LIVE_DB_PASSWORD=live_litellm_password
```

(Repeat pattern for any other service with dev/live tiers.)

### 2. Update `db-bootstrapper` in `docker-compose.platform.yml`

Change the `command` box. Options:

- **Option A (preferred):** Replace the SQL-file runner with an inline Python/psql script that loops over per-env users/dbs from env vars. Avoids SQL injection, keeps logic in code not stored procedures.
- **Option B:** Keep SQL files but generate them dynamically as a mounted file (e.g. a small Python entrypoint rendering `001/002/003` from env) — but this adds generated artifacts that `db-setup` was meant to avoid.
- **Option C:** Move user creation into the `migrate` container as a `000_seed_users.goose.sql` migration. Goose can run any SQL.

**Recommended:** Option A — replace the `db-setup` volume mount and inline psql loops with a `bootstrap.py` script in `ai-assistant-infra/scripts/` that:
1. Connects to `postgres` as superuser.
2. Creates per-env DBs if missing (same set as current 001).
3. Creates per-env DB users with random or env passwords.
4. `GRANT CONNECT`, `ALTER DATABASE OWNER`, `ALTER SCHEMA public OWNER`.

The `migrate` service then runs goose schema-only migrations after `db-bootstrapper` exits successfully.

### 3. Update `migrate` + agentic services for per-env creds

In `docker-compose.yml`, every agentic service already declares `DATABASE_URL`, `DATABASE_URI`, etc. using `*_DEV_*` or `*_LIVE_*` vars. Verify they point to the correct per-env user/password:

- `workflow-engine` live: `${AIASSIST_DB_USER}:${AIASSIST_DB_PASSWORD}@postgres:5432/${AIASSIST_LIVE_DB_NAME}` → change to `${AIASSIST_LIVE_DB_USER}:${AIASSIST_LIVE_DB_PASSWORD}@postgres:5432/${AIASSIST_LIVE_DB_NAME}`
- `langgraph` live: `${LANGGRAPH_DB_USER}:${LANGGRAPH_DB_PASSWORD}@postgres:5432/${LANGGRAPH_LIVE_DB_NAME}` → change to `${LANGGRAPH_LIVE_DB_USER}:${LANGGRAPH_LIVE_DB_PASSWORD}@postgres:5432/${LANGGRAPH_LIVE_DB_NAME}`
- Same pattern for `litellm`, dev-tier equivalents, and any remaining services pointing at `AIASSIST_DB_NAME` with the shared `AIASSIST_DB_USER`.

### 4. Remove `db-setup` from `db-bootstrapper` volume mount

`ai-assistant-infra/db-setup/` and its `bootstrap.sh` / `orchestrator.js` are now unused by the platform compose. The bootstrap logic lives in `db-bootstrapper` inline or in `ai-assistant-infra/scripts/bootstrap.py`. Remove the `volumes: - ./ai-assistant-infra/db-setup:/db-setup` line.

### 5. TeamCity vars

TeamCity already has `TEAMCITY_DB_NAME`, `TEAMCITY_DB_USER`, `TEAMCITY_DB_PASSWORD` in `.env.template`. Keep these; no extension needed unless the user wants a second TeamCity DB for CI vs instance (out of scope unless requested).

## Risks

- Removing `db-setup` volume mount breaks any external callers (none currently per-codebase inspection; `docker-compose.platform.yml` is the only consumer).
- Inline bootstrap script must be idempotent (retain `WHERE NOT EXISTS` semantics).

## Files

- **Edit** `.env.template` — add per-env DB user/password vars.
- **Edit** `docker-compose.platform.yml` — `db-bootstrapper` command + remove db-setup volume.
- **Edit** `docker-compose.yml` — fix connection strings to use per-env users.
- **Create** `ai-assistant-infra/scripts/bootstrap.py` (or similar) — replace SQL bootstrapper.
