# CI/CD

Continuous delivery is provided by **Gitea Actions** with a stateless runner container. The `delivery` Python CLI is a thin orchestrator that discovers packages, resolves providers, and executes declared build/test/deploy contracts. Gitea is the VCS source of truth.

## Topology

```
Gitea (ai/aiassistant)  ──triggers──▶  Gitea Actions runner  ──invokes──▶  delivery CLI
    (repo + workflows)                     (docker)                     (discover → build → test → deploy)
```

- **Workflows:** thin YAML in `.gitea/workflows/*.yml` that invoke `delivery` commands.
- **Runner:** `gitea-runner` container with host Docker socket access.
- **Packages:** each deployable unit lives under `packages/*/` with a `package.yaml` manifest.
- **Providers:** language-specific implementations (Python, TypeScript, Go, Rust) that know how to build/test each package type.
- **Registry auth:** flows through environment `.env` files or Gitea Actions secrets; never committed to Git.

## Test Layers

Tests are organised into three distinct layers. Each layer has a different purpose, runtime requirement, and feedback speed.

| Layer | Name | Scope | Runtime | How to run |
|---|---|---|---|---|
| **1** | Unit | Single class/function, all dependencies mocked | Sub-millisecond | `pytest tests/ -m unit` |
| **2** | Application Integration | Real app code path, infrastructure adapters mocked, no Docker | Seconds | `pytest packages/workflow_runner/tests/test_platform_integration.py` |
| **3** | Platform E2E | Full Docker Compose stack + browser automation | Minutes | `.woodpecker.yml → test-e2e` |

### Layer 1 — Unit
- Pure Python/TypeScript unit tests.
- No `TestClient`, no Docker, no network.
- Fast feedback during local development.

### Layer 2 — Application Integration
- Uses FastAPI `TestClient` or equivalent in-process runner.
- Infrastructure dependencies (EventBus, Scheduler, Database, LLM) are patched/mocked at the adapter boundary.
- The AssistantChatService, context formation, validation loops, and Work delegation are exercised with real code.
- Can run locally without Docker.
- **Canonical file:** `packages/workflow_runner/tests/test_platform_integration.py`

### Layer 3 — Platform E2E
- Requires full Docker Compose stack: `infrastructure/compose.yml` → `platform/compose.yml` → `environments/dev/compose.yml`.
- Playwright browser tests validate the running platform end-to-end.
- Artifacts (HTML report, JUnit XML, traces) are collected by CI.
- **Canonical file:** `packages/control-center-ui/tests/e2e/critical-path.spec.ts`

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `.gitea/workflows/pr.yml` | Pull request to `main` | Unit tests |
| `.gitea/workflows/main.yml` | Push to `main` | Discover → test → build → publish → deploy dev → validate |
| `.gitea/workflows/promote.yml` | Manual dispatch | Promote to live |

## Delivery engine

| Component | Responsibility |
|---|---|
| **Package Registry** | Discovers and indexes `packages/*/package.yaml` |
| **Provider Registry** | Maps package `type` → language-specific Provider |
| **Execution Engine** | Orchestrates build, test, publish, deploy |

The engine is language-agnostic. Adding a new language requires implementing a new Provider; no engine changes needed.

## Package metadata

Each package declares itself with `package.yaml`:

| Field | Purpose |
|---|---|
| `name` | Package identifier |
| `version` | Semantic version |
| `type` | Language/runtime (`python`, `typescript`, `go`, `rust`) |
| `kind` | `service`, `library`, `tool`, `plugin` |
| `provides` | Capabilities this package implements |
| `deployable` | Whether this package produces a runtime artifact |
| `dockerfile` | Path to Dockerfile |
| `depends_on` | Package dependencies (for future dependency graph) |

## Bootstrap

1. Bring up infrastructure + platform (`infrastructure/compose.yml`, `platform/compose.yml`).
2. Ensure `.gitea/workflows/*.yml` are present in the repo.
3. Enable Gitea Actions in Gitea admin settings and register the runner.
