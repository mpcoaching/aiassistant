# CI/CD

## Source of truth

**GitHub is the authoritative repository.** Developers push to GitHub and never to Gitea.

**Gitea is a pull mirror of GitHub, used only as the CI/CD source.** Gitea is not a second source of truth: it is a read-only mirror (`remote: mirror repository is read-only` on any push attempt) whose sole purpose is to make commits available to Woodpecker, which is integrated with Gitea rather than GitHub.

## Topology

```
GitHub (ai/aiassistant)          authoritative; recovery source
      │  pull mirror (Gitea fetches from GitHub on an interval)
      ▼
Gitea (ai/aiassistant)           read-only CI/CD mirror
      │  push webhook → Woodpecker
      ▼
Woodpecker server + agent       executes .woodpecker/*.yaml
      │
      ▼
Container registry + Compose    deploy → n8n (deployment target)
```

The GitHub → Gitea hop is **pull-based by necessity**: GitHub is authoritative but passive — it receives pushes and does not push onward — so Gitea must fetch. Two native Gitea mechanisms perform that fetch, and only these:

- the `update_mirrors` cron task (enabled, `@every 10m`), and
- on-demand sync (`POST /repos/{owner}/{repo}/mirror-sync`, the UI's **Sync now**).

The per-repository `mirror_interval` is set to `10m`, which is Gitea's hard minimum; 5m is rejected with `invalid mirror interval: 5m0s is below minimum interval: 10m0s`. Changing the interval does not recompute a mirror's already-scheduled next-sync time, so the first sync after an interval change must be triggered manually before the new cadence takes effect.

The Gitea → Woodpecker hop is **webhook-based**: an active repo-level webhook delivers `push` events to `https://woodpecker.local.test/api/hook`.

## Components

- **CI/CD engine:** Woodpecker `v3` server + agent (`infrastructure/compose.yml`), Docker backend via the host socket.
- **Workflows:** `.woodpecker/ci.yaml` (build, test, push, e2e, dev deploy) and `.woodpecker/deploy.yaml` (platform/n8n deploy). The `ci` workflow clones from Gitea over plain HTTP; `deploy.yaml` sets `skip_clone` and runs against the host checkout bind-mounted at its real path.
- **Legacy:** `.gitea/workflows/*.yaml` targets the retired Gitea Actions topology and is no longer on the CI path.
- **Registry auth:** flows through Woodpecker secrets sourced from environment `.env` files; never committed to Git.

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
| `.woodpecker/ci.yaml` | Push (or manual) | install → test-custom-nodes → validate-contracts → lint → test → build → push → test-e2e → deploy |
| `.woodpecker/deploy.yaml` | Push to `main` touching `platform/compose.yml` or `custom-nodes/**` | `deploy-platform`: check out the exact SHA and force-recreate the authoritative n8n service |

`deploy.yaml` is path-filtered on purpose. n8n reads `N8N_CUSTOM_EXTENSIONS` only at process start and the nodes arrive via a bind mount, so a change under `custom-nodes/**` causes no Compose config drift and therefore no automatic recreate. The step always passes `--force-recreate`.

## Delivery engine (not on the CI path)

The `delivery/` CLI and the `package.yaml` manifests below describe the retired Gitea Actions
topology. The code is still present but Woodpecker does not invoke it; CI/CD is executed by the
steps in `.woodpecker/*.yaml`. Kept for reference only.

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

1. Bring up infrastructure (`infrastructure/compose.yml`), which runs Gitea, Woodpecker
   server/agent, the registry, and CoreDNS.
2. Ensure the Gitea repository exists as a **pull mirror** of GitHub, pointing at
   `https://github.com/<owner>/aiassistant.git`, with `mirror_interval` at `10m`. This requires
   `GITEA__MIGRATIONS__ALLOWED_DOMAINS` to include the upstream host.
3. Ensure the repository is **activated in Woodpecker** (Woodpecker's own repository list). Until
   it is, Gitea's push webhook is accepted and then discarded because no matching repository is
   registered, and no pipeline is ever created.
4. Verify the chain end to end: a push to GitHub appears in Gitea within the mirror interval, and
   Woodpecker opens a pipeline for it.
