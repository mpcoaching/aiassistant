# Runbook — Recovery (Backup & Restore)

Rule: **a backup is not complete until its restore is tested.** Restore tests use scratch targets,
never production-named volumes/databases.

## Backup (schedule)
```bash
bash cicd/scripts/backup-all.sh        # Postgres + registry + Gitea
```
Outputs timestamped dirs under `./backups/`. Also capture config state:
```bash
git tag -a backup-$(date +%Y%m%d) -m "Config state at promoted SHA $(git rev-parse --short HEAD)"
# encrypt + store .env out of band:
gpg -c .env        # keep .env.gpg in the secure backup location
```

## Postgres restore (tested)
```bash
# restore a single DB into a SCRATCH database, verify, drop
bash cicd/scripts/restore-test-postgres.sh backups/postgres/<ts>/agent_dev.dump agent_dev_restore_test

# real restore (only when needed): restore into the real DB after stopping writers
export PGPASSWORD="$POSTGRES_DB_PASSWORD"
psql -h postgres -U postgres -c 'DROP DATABASE IF EXISTS "agent_live";'
psql -h postgres -U postgres -c 'CREATE DATABASE "agent_live" OWNER "agent_live_user";'
pg_restore -h postgres -U postgres --no-owner --no-privileges -d agent_live backups/postgres/<ts>/agent_live.dump
```

## Registry restore (tested)
```bash
bash cicd/scripts/restore-test-registry.sh backups/registry/<ts>/registry_data.tar
# real restore: stop registry, swap in the restored volume, start
```

## Gitea restore
1. `docker stop infra_gitea`.
2. Restore `/data` from the `gitea dump` into a temp Gitea container.
3. Verify a repo + webhook exist, then promote the temp data into `gitea_data` and start.

## Phase 7.5 gate
Before the **first** Live promotion, run the automated restore tests and create the green marker:
```bash
bash cicd/scripts/validate-backups.sh     # touches cicd/state/backup-validation-green
```
`deploy-live.sh` refuses to proceed until that marker exists. Re-run `validate-backups.sh` whenever
the backup procedure changes.

## RTO / RPO notes
- Postgres + registry are the critical backups; Gitea is recoverable from VCS + volumes.
- Test restores on a schedule (e.g. monthly) so the green marker reflects reality.
