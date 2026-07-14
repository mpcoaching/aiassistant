# Operations

Day-to-day operation, backup, and restore procedures. The guiding rule:
**a backup is not complete until its restore is tested.** See `docs/runbooks/runbook-recovery.md`
for the step-by-step restore runbook.

## Bring up / down

See `docs/runbooks/runbook-startup.md` and `runbook-shutdown.md`. Order matters:
infrastructure first (creates networks), then platform, then dev/live.

## Backups (idempotent, non-destructive)

Scripts under `cicd/scripts/` write timestamped directories under `./backups/`.

| Script | What it backs up |
|---|---|
| `backup-postgres.sh` | `pg_dump -Fc` per database (`agent_dev`, `agent_live`, platform DBs) |
| `backup-registry.sh` | tar of the `registry_data` volume |
| `backup-gitea.sh` | `gitea dump` |
| `backup-teamcity.sh` | tar of `teamcity_data` + `teamcity_logs` volumes |
| `backup-all.sh` | runs all of the above |

Config state is captured by **git tagging at the promoted SHA** plus an encrypted copy of `.env`
(see `runbook-recovery.md`).

## Restore tests (Phase 7.5 gate)

Before the **first** Live promotion (and periodically after), run restore tests against scratch
targets — never against production-named volumes:

1. **Postgres** — `restore-test-postgres.sh <dump> agent_dev_restore_test` → restores into a scratch
   DB, prints row counts, drops the scratch DB.
2. **Registry** — `restore-test-registry.sh <tar>` → imports into a temp registry container, pulls a
   known image, stops the temp registry.
3. **Gitea** — import a `gitea dump` into a temp Gitea; verify a repo + webhook exist.
4. **TeamCity** — restore `teamcity_data`; verify the server starts and settings load from VCS.
5. **Config** — confirm the git tag at the promoted SHA + encrypted `.env` copy exist.

`cicd/scripts/validate-backups.sh` runs the automated tests (1–2) and creates
`cicd/state/backup-validation-green`, which `deploy-live.sh` requires.

## Volumes (persistent state — never auto-deleted)

`postgres_db`, `qdrant_data`, `rabbitmq_data`, `redis_agents_data`, `langfuse_*`, `clickhouse_data`,
`openobserve_storage`, `minio_data`, `n8n_data`, `gitea_data`, `teamcity_data`, `teamcity_logs`,
`teamcity_agent_conf`, `registry_data`, `dind_data`, `langgraph_config`.

## Secrets

`.env` holds all secrets. It is **never** committed; an encrypted copy is part of the backup set.
Rotate via the documented procedure in `runbook-recovery.md` and update TeamCity password params for
the registry.

## Health

- `nginx-proxy`: `nginx -t` healthcheck.
- `postgres`: `pg_isready`.
- `clickhouse`: `clickhouse-client SELECT 1`.
- `registry`: `registry garbage-collect --dry-run` healthcheck.

`docker network ls --filter name=network` should show the four networks.
