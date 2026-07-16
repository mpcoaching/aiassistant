# AI Assistant Platform

Capability-oriented SaaS deployment platform using **Gitea Actions** for CI/CD and a Python `delivery` CLI for package-based delivery.

## Quick start

```bash
docker compose -f infrastructure/compose.yml -f platform/compose.yml up -d
```

## Repository structure

```
packages/
  workflow-runner/     ← Python service (workflow execution)
  control-center-ui/   ← TypeScript/React UI
  langgraph/           ← Python library (graph orchestration)
  opencode/            ← Python service (OpenCode agent runtime)
  autogen/             ← Python service (AutoGen agent runtime)

platform/
  tests/
    integration/
    e2e/
    perf/
    security/

delivery/              ← Package-based delivery engine

environments/
  dev/
    compose.yml
  live/
    compose.yml
```

## Delivery CLI

```bash
pip install -r delivery/requirements.txt
delivery discover
delivery build workflow-runner
delivery test workflow-runner unit
delivery publish workflow-runner
delivery deploy dev workflow-runner
```

## CI/CD

- **PR pipeline:** `.gitea/workflows/pr.yml` — unit tests on PR
- **Main pipeline:** `.gitea/workflows/main.yml` — discover → test → build → publish → deploy dev → validate
- **Promotion:** `.gitea/workflows/promote.yml` — promote to live

## Architecture

- **Gitea** is the source of truth for code and pipelines.
- **Gitea Actions** runner executes workflows.
- **delivery CLI** is a thin orchestrator: discovers packages, resolves providers, executes build/test/publish/deploy contracts.
- **Providers** encapsulate language-specific behavior (Python, TypeScript, Go, Rust).
- **Registry** stores immutable images tagged by git-sha.
