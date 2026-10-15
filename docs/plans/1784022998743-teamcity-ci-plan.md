# Delivery Architecture — Gitea Actions

## ADR-001: Replace TeamCity with Gitea Actions and Capability-Oriented Delivery

**Status:** Accepted  
**Date:** 2026-07-15  
**Deciders:** Platform team

### Context

TeamCity was selected as the CI/CD platform, but the implementation revealed fundamental architectural problems:

- **Hidden state**: Build configurations live in TeamCity's database. A server rebuild loses all pipeline definitions.
- **Broken Kotlin DSL**: The internal Maven repository required for Kotlin DSL compilation is inaccessible in our Docker environment, producing 173+ compilation errors.
- **Proprietary DSL**: Even if fixed, Kotlin DSL is not reproducible from Git alone — it requires the TeamCity server runtime to compile.
- **Operational burden**: TeamCity requires its own server, agent, and database. It increases complexity rather than reducing it.
- **Not AI-editable**: Kotlin DSL is error-prone for AI agents. YAML is predictable and widely understood.

### Decision

Replace TeamCity entirely with **Gitea Actions** and a **capability-oriented delivery CLI** built in Python (Typer).

### Rationale

1. **Gitea Actions** eliminates the CI server operational burden. The runner is a stateless Docker container. Pipelines are YAML files in Git.
2. **Capability-oriented design** separates orchestration from implementation. Gitea Actions contains only workflow logic. All delivery logic lives in a single Python CLI (`delivery`).
3. **Immutable image promotion** ensures the exact same artifact is deployed to every environment. No rebuilds, no drift.
4. **Registry-based deployment** makes the container registry the source of truth for runtime artifacts. Git describes desired state; the registry holds immutable images.
5. **Python CLI** is testable, structured, extensible, and self-documenting. It can grow into a long-lived platform component.

### Consequences

- **Positive**: No hidden state. Everything is in Git or the registry.
- **Positive**: AI agents can edit workflows and invoke the CLI without learning proprietary systems.
- **Positive**: Local development workflow is identical to CI workflow (`delivery build`, `delivery deploy dev ...`).
- **Negative**: Gitea Actions may lack some TeamCity plugins. We accept this trade-off for simplicity.
- **Negative**: Migration effort required to rebuild pipelines in Gitea Actions.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Fix Kotlin DSL | Fragile in Docker. Server-side compilation means pipelines are not reproducible from Git alone. |
| TeamCity YAML Pipelines | Still requires TeamCity server runtime. |
| GitHub Actions | Requires pushing to GitHub for CI. Gitea is the canonical local source of truth. |
| Jenkins | More operational complexity. Groovy pipelines are harder to maintain. |

---

## Capability Model

The delivery subsystem is modeled as **capabilities**, not a pipeline. Orchestration (Gitea Actions) invokes these capabilities in sequence. Each capability is a subcommand of the `delivery` CLI.

| Capability | Responsibility | CLI Subcommand |
|------------|---------------|----------------|
| **Build** | Build Docker images using buildx | `delivery build` |
| **Test** | Execute unit, integration, E2E tests | `delivery test` |
| **Publish** | Push/pull images to/from registry | `delivery publish` |
| **Deploy** | Reconcile desired state via Docker Compose | `delivery deploy` |
| **Validate** | Health checks, smoke tests, coverage ratchet | `delivery validate` |
| **Promote** | Validate and promote release between environments | `delivery promote` |
| **Rollback** | Deploy previous known-good release | `delivery rollback` |
| **Status** | Show release/deployment status | `delivery status` |
| **Doctor** | Verify environment prerequisites | `delivery doctor` |
| **Backup** | Backup runtime state | `delivery backup` |
| **Restore** | Restore runtime state | `delivery restore` |
| **Logs** | Stream/search deployment logs | `delivery logs` |

**Key principle:** Capabilities are reusable. Orchestration decides when to invoke them. A human operator can invoke any capability directly.

---

## Release Model

A **Release** is the immutable deployment object. It is not a Git SHA alone.

### Release Metadata

```yaml
release:
  id: "abc123def456"               # Git SHA (unique identifier)
  image_digests:
    workflow-runner: "sha256:abcdef..."
    control-center-ui: "sha256:123456..."
    langgraph: "sha256:789abc..."
  test_results:
    unit: "passed"                  # unit/integration/e2e
    integration: "passed"
    e2e: "skipped"
  migration_version: "20260715_001"
  build_timestamp: "2026-07-15T10:30:00Z"
  builder: "gitea-runner"
  environments:
    dev:
      status: deployed
      deployed_at: "2026-07-15T10:32:00Z"
      compose_file: "environments/dev/compose.yml"
    live:
      status: pending
```

### Release Storage

**Runtime store only.** Never committed to Git.

- **Store:** SQLite database at `delivery/state/delivery.db` (mounted volume)
- **Tables:** `releases`, `deployments`, `validation_results`
- **Access:** `delivery status <sha>` queries the runtime store
- **Backup:** Included in `delivery backup` / `delivery restore`

### Why a Release object

- Git SHA alone is insufficient — it doesn't capture image digests, test status, or deployment history.
- A Release is the immutable deployment unit. It references everything needed to reproduce or rollback.
- AI agents can query `delivery status` to understand deployment history without reading Git logs.
- Separation of concerns: Git = desired state. Registry = immutable images. Runtime store = deployment history.

---

## Delivery CLI Design

### Technology

- **Language:** Python 3.11+
- **Framework:** Typer (CLI), Rich (output), SQLite (runtime store)
- **Entry point:** `delivery/delivery` (console script)
- **Structure:** Single package with subcommands

### Interface

```bash
delivery <command> [options] [args...]
```

### Subcommands

| Command | Purpose | Example |
|---------|---------|---------|
| `build` | Build images with buildx | `delivery build workflow-runner control-center-ui` |
| `test` | Run tests | `delivery test unit --coverage` |
| `publish` | Push/pull images | `delivery publish workflow-runner control-center-ui` |
| `deploy` | Deploy to environment | `delivery deploy dev abc123def` |
| `validate` | Run validation checks | `delivery validate dev` |
| `promote` | Promote release to environment | `delivery promote dev live abc123def` |
| `rollback` | Rollback to previous release | `delivery rollback live` |
| `status` | Show release/deployment status | `delivery status abc123def` |
| `doctor` | Verify prerequisites | `delivery doctor` |
| `backup` | Backup runtime state | `delivery backup --output backup.tar.gz` |
| `restore` | Restore runtime state | `delivery restore backup.tar.gz` |
| `logs` | Stream/search deployment logs | `delivery logs dev --follow` |

### Implementation

**Structure:**
```
delivery/
├── delivery/
│   ├── __init__.py
│   ├── cli.py              # Typer app definition
│   ├── commands/
│   │   ├── build.py
│   │   ├── test.py
│   │   ├── publish.py
│   │   ├── deploy.py
│   │   ├── validate.py
│   │   ├── promote.py
│   │   ├── rollback.py
│   │   ├── status.py
│   │   ├── doctor.py
│   │   ├── backup.py
│   │   ├── restore.py
│   │   └── logs.py
│   ├── lib/
│   │   ├── docker.py       # Docker/buildx abstraction
│   │   ├── registry.py     # Registry operations
│   │   ├── compose.py      # Compose file management
│   │   ├── release.py      # Release metadata management
│   │   └── store.py        # SQLite runtime store
│   └── models.py           # Release, Deployment, ValidationResult dataclasses
├── pyproject.toml
└── README.md
```

**Dependencies:** `typer`, `rich`, `docker`, `sqlite3` (stdlib), `pyyaml`, `requests`

**Encapsulation principle:** Docker-specific implementation details are hidden behind capability commands. Future runtime technologies can be adopted by modifying `lib/docker.py` and `lib/compose.py` without changing orchestration workflows.

### Build Implementation (docker buildx)

```python
# delivery/commands/build.py
def build(services: list[str], tag: str):
    """Build images using docker buildx with parallel execution."""
    # Use buildx with --builder=default (or create dedicated builder)
    # Build in parallel where dependencies allow
    # Tag with git-sha, store digest for release metadata
```

**Parallel builds:** Buildx builds independent service images in parallel. Services with no shared build context can be built concurrently.

---

## Registry as First-Class Component

### Lifecycle

```
Source Code → Build → Image → Registry → Promotion → Deployment → Runtime
```

### Registry Strategy

**Single registry, multiple environments:**
- Registry: `gitea.local.test:5000/aiassistant`
- Images tagged with immutable git-sha
- Same image promoted from dev → live
- No `latest` tag used in production

**Image naming:**
```
registry/aiassistant/workflow-runner:<git-sha>
registry/aiassistant/control-center-ui:<git-sha>
registry/aiassistant/langgraph:<git-sha>
```

---

## Configuration Strategy

### Configuration Taxonomy

| Class | Examples | Where | Version Controlled | Access |
|-------|----------|-------|-------------------|--------|
| **Image tags** | Git SHA | CI environment variable | Implicitly yes | CI, deployment |
| **Environment variables** | `DATABASE_URL`, `ENV_TIER` | `.env` file per environment | Template only | Runtime |
| **Secrets** | `REGISTRY_PASSWORD`, `API_KEY` | Gitea Actions secrets + `.env` | Never | Runtime only |
| **Feature flags** | `ENABLE_NEW_FEATURE` | `.env` or compose label | If stable, yes | Runtime |
| **Tenant configuration** | Per-tenant DB names | `.env` or tenant files | No | Runtime |
| **Docker Compose overrides** | `environments/{env}/compose.yml` | Git | Yes | Deployment |
| **Release metadata** | Image digests, test results | SQLite runtime store | Never | Runtime |

### Rules

1. **Git contains everything needed to deploy.** A fresh clone can deploy any known-good SHA.
2. **`.env` is never in Git.** `.env.template` documents required variables.
3. **Secrets flow through Gitea Actions secrets or environment-specific `.env` files.**
4. **Compose files are immutable per environment.**
5. **Release metadata lives in the runtime store, not Git.**

---

## Repository Layout

**Target structure:**
```
aiassistant/
├── .gitea/
│   └── actions/
│       └── workflows/          # Gitea Actions orchestration (thin)
├── delivery/                   # Delivery capability implementation
│   ├── delivery/               # Python CLI package
│   │   ├── cli.py
│   │   ├── commands/           # Subcommand implementations
│   │   ├── lib/                # Docker/registry/compose abstractions
│   │   └── models.py           # Release, Deployment dataclasses
│   ├── pyproject.toml
│   └── README.md
├── environments/               # Environment compose files
│   ├── dev/
│   │   └── compose.yml
│   └── live/
│       └── compose.yml
├── infra/                      # Infrastructure configs
│   ├── wait_for.py
│   ├── db-setup/
│   ├── migrations/
│   └── configs/
├── agents/                     # Application code + Dockerfiles
│   ├── workflow-runner/
│   ├── control-center-ui/
│   └── langgraph/
├── docker-compose.platform.yml # Shared infrastructure
├── docker-compose.yml           # Dev/live app services
├── .env.template
└── .env                        # Not in Git
```

**What disappears:**
- `cicd/` — replaced by `delivery/`
- `cicd/teamcity/` — TeamCity configs deleted
- `cicd/scripts/*.sh` — consolidated into Python CLI
- `.github/workflows/` — deprecated

---

## Orchestration Layer

**Location:** `.gitea/actions/workflows/*.yml`

**Principle:** Workflows are thin. They invoke `delivery` CLI subcommands. No deployment logic lives in YAML.

**Example:**
```yaml
jobs:
  main:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r delivery/requirements.txt
      - run: delivery doctor
      - run: delivery build workflow-runner control-center-ui
      - run: delivery publish workflow-runner control-center-ui
      - run: delivery deploy dev ${{ github.sha }}
      - run: delivery validate dev
```

---

## Migration Plan

### Phase 1: Foundation (Week 1)

1. Create `delivery/` Python package with Typer CLI skeleton
2. Implement core subcommands: `doctor`, `build`, `publish`, `deploy`, `validate`, `status`
3. Implement runtime store (SQLite) for releases and deployments
4. Add `gitea-runner` service to `docker-compose.platform.yml`
5. Enable Gitea Actions in Gitea admin settings

### Phase 2: PR Pipeline (Week 1)

1. Create `.gitea/actions/workflows/pr.yml` — lint + unit tests
2. Wire `delivery test unit` into workflow
3. Verify PR pipeline runs
4. Merge to main

### Phase 3: Main Pipeline (Week 2)

1. Create `.gitea/actions/workflows/main.yml` — build → publish → deploy dev → validate
2. Wire `delivery build`, `delivery publish`, `delivery deploy`, `delivery validate`
3. Test on feature branch, then main
4. Verify dev deployment

### Phase 4: Promotion (Week 2)

1. Create `.gitea/actions/workflows/promote.yml`
2. Wire `delivery promote dev live <sha>`
3. Test promotion and rollback

### Phase 5: Remove TeamCity (Week 3)

1. Remove TeamCity services from `docker-compose.platform.yml`
2. Remove `cicd/` directory
3. Remove `.github/workflows/`
4. Clean nginx/dnsmasq configs
5. Update README

### Phase 6: Validate (Week 3)

1. End-to-end test: PR → merge → dev → promote → live
2. Rollback test
3. Backup/restore test
4. Document runbooks

---

## Observability

### What to log

- Build start/end with Git SHA and image digests
- Test results (pass/fail count)
- Registry push/pull events
- Deployment start/end per environment
- Health check results
- Rollback events

### Where logs live

- **CI logs**: Gitea Actions job logs (built-in)
- **Application logs**: Container stdout, collected by Docker
- **Deployment logs**: `delivery/state/deployments/<env>/<sha>.log` (runtime volume)
- **Release metadata**: SQLite runtime store

---

## Risks

| Risk | Mitigation |
|------|------------|
| Gitea Actions feature gaps | Evaluate early. Fallback: GitHub Actions if needed. |
| Runner resource contention | Dedicated labels, limit concurrent jobs. |
| Registry performance | Monitor, add caching if needed. |
| Secret exposure | Use Gitea secret masking, audit logs. |
| Deployment drift | `delivery validate` enforces immutable references. |
| Single point of failure (Gitea) | Backup strategy. |
| CLI complexity creep | Keep single package, limit subcommands, use Typer's self-documentation. |

---

## Trade-offs

| Trade-off | Decision |
|-----------|----------|
| **Simplicity vs Features** | Chosen simplicity. Gitea Actions covers our needs. |
| **Gitea vs GitHub Actions** | Chose Gitea for self-hosting. |
| **Docker Compose vs Kubernetes** | Chose Compose for simplicity. |
| **Python CLI vs Bash** | Chose Python for testability and structure. |
| **YAML vs DSL** | Chose YAML for AI-editability. |
| **Runtime store vs Git for history** | Chose SQLite. Git is for desired state, not runtime history. |

---

## Validation Plan

**Smoke tests after each phase:**
- Workflow triggers on correct events
- Jobs complete successfully
- Artifacts are produced
- Deployments reach target environment
- Health checks pass
- Secrets are not exposed in logs

**End-to-end validation:**
1. Open PR → lint + tests pass
2. Merge to main → dev deployment succeeds
3. Integration tests pass on dev
4. Promote to live → live deployment succeeds
5. Rollback to previous SHA → live recovers

---

## Open Questions

1. **Gitea Actions version:** Which Gitea version are we running? Need to verify Actions support level.
2. **Registry choice:** Gitea built-in registry vs separate container? Built-in is simpler.
3. **Backup automation:** Cron job or Gitea Action? Cron is simpler for periodic backups.
4. **Monitoring scope:** Keep Langfuse + OpenObserve, or simplify further?
