# AI Assistant Platform

Capability-oriented SaaS deployment platform using **Gitea Actions** for CI/CD and a Python `delivery` CLI for immutable image promotion.

## Quick start

```bash
docker compose -f infrastructure/compose.yml -f platform/compose.yml up -d
```

## Delivery CLI

```bash
pip install -r delivery/requirements.txt
delivery doctor
delivery build workflow-runner control-center-ui
delivery publish workflow-runner control-center-ui
delivery deploy dev <git-sha>
delivery validate dev
delivery promote dev live <git-sha>
```

## CI/CD

- **PR pipeline:** `.gitea/actions/workflows/pr.yml` — lint + unit tests
- **Main pipeline:** `.gitea/actions/workflows/main.yml` — build → publish → deploy dev → validate
- **Promotion:** `.gitea/actions/workflows/promote.yml` — promote dev → live

## Architecture

- **Gitea** is the source of truth for code and pipelines.
- **Gitea Actions** runner executes workflows.
- **delivery CLI** implements capabilities: build, test, publish, deploy, validate, promote, rollback, status, doctor, backup, restore, logs.
- **Registry** stores immutable images tagged by git-sha.
- **Release metadata** lives in SQLite at `delivery/state/delivery.db`.
