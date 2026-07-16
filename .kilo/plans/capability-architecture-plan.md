# Capability-Based Architecture Plan

## Core principle

Treat the repository as a **registry of capabilities**, not as “a folder containing code.”

Each capability is a first-class unit that owns its code, tests, build rules, deployment metadata, and documentation. The delivery system doesn’t care what language a capability uses — it just knows how to discover capabilities and invoke their declared build/test/deploy contracts.

---

## 1. Repository layout

```
capabilities/
  workflow-runner/
    package.yaml
    pyproject.toml
    src/workflow_runner/
    tests/
    Dockerfile
    README.md

  control-center-ui/
    package.yaml
    package.json
    tsconfig.json
    src/
    tests/
    Dockerfile
    README.md

  langgraph/
    package.yaml
    pyproject.toml
    src/langgraph/
    tests/
    Dockerfile
    README.md

  opencode/
    package.yaml
    pyproject.toml
    src/opencode/
    tests/
    Dockerfile
    README.md

  autogen/
    package.yaml
    pyproject.toml
    src/autogen/
    tests/
    Dockerfile
    README.md

platform/
  tests/
    integration/
    e2e/
    perf/
    security/

delivery/
  (CLI tool — reads package.yaml, discovers capabilities)

environments/
  dev/
    compose.yml
  live/
    compose.yml

docs/
  architecture.md
  delivery.md
  operations.md
  runbooks/
```

**Why `capabilities/`?** It matches the capability-oriented architecture you’ve been building. It also scales cleanly when new capability types appear (workers, gateways, plugins, etc.).

**Why not `packages/` or `services/`?** Both are viable, but `packages/` implies language-specific packaging, and `services/` implies runtime topology. `capabilities/` is neutral and intent-revealing.

---

## 2. Package metadata (package.yaml)

Every capability declares itself with a small manifest. The delivery engine reads this rather than inferring structure from file extensions.

```yaml
# capabilities/workflow-runner/package.yaml
name: workflow-runner
version: 0.1.0
description: Workflow runner service

# Language/runtime type — the delivery engine uses this to select tooling
# Supported: python, typescript, go, rust, ...
type: python

# Build contract
build:
  # How to produce a deployable artifact
  command: docker build -t ${REGISTRY}/aiassistant/workflow-runner:${VERSION} .
  # Optional: multi-stage build, build args, etc.

# Test contracts
test:
  unit:
    command: pytest tests/ -v
    coverage:
      command: pytest tests/ --cov=src --cov-report=term-missing
      threshold: 80
  integration:
    command: pytest platform/tests/integration/ -v -k workflow-runner

# Runtime
docker:
  image: ${REGISTRY}/aiassistant/workflow-runner:${VERSION}
  compose: environments/dev/compose.yml
  service: workflow-runner

# Dependencies (for future dependency graph support)
depends_on:
  - postgres
  - redis

# Tags for filtering
tags:
  - backend
  - core
```

```yaml
# capabilities/control-center-ui/package.yaml
name: control-center-ui
version: 0.1.0
description: Control center web UI

type: typescript

build:
  command: docker build -t ${REGISTRY}/aiassistant/control-center-ui:${VERSION} .

test:
  unit:
    command: vitest run tests/unit
  e2e:
    command: vitest run tests/e2e

docker:
  image: ${REGISTRY}/aiassistant/control-center-ui:${VERSION}
  compose: environments/dev/compose.yml
  service: control-center-ui

depends_on: []
tags:
  - frontend
  - ui
```

**Design decision:** `package.yaml` is the *single source of truth* for delivery metadata. Language-specific files (`pyproject.toml`, `package.json`) remain for their respective tooling, but the delivery engine never parses them directly.

---

## 3. Language-agnostic delivery engine

The engine operates on **packages**, not file types.

### 3.1 Discovery

```
scan capabilities/*/package.yaml
→ list of capabilities
```

### 3.2 Change detection (future)

```
git diff --name-only main..HEAD
→ map changed files to capabilities
→ build only affected capabilities
```

First implementation: rebuild everything. Architecture supports incremental later.

### 3.3 Build

For each capability:
1. Read `package.yaml`
2. Execute `build.command`
3. Tag artifact with `${VERSION}` (git SHA or semver)

### 3.4 Test

For each capability:
1. Read `package.yaml`
2. Execute `test.unit.command`
3. If coverage: execute `test.unit.coverage.command` and enforce threshold
4. Execute `test.integration.command` if defined

### 3.5 Deploy

For each capability:
1. Read `package.yaml`
2. Execute `docker.compose` with the specified service
3. Record deployment in runtime store

**No more:** `from .models import ...`, `agents/*/tests`, `*.py` scanning, hardcoded service lists.

---

## 4. Package independence

Every capability is independently executable:

```bash
cd capabilities/workflow-runner
pytest tests/ -v

cd capabilities/control-center-ui
vitest run tests/unit
```

The `delivery` CLI is just an orchestrator. Developers can work inside a single capability without understanding the rest of the repo.

---

## 5. Test separation

| Directory | Purpose | Scope |
|---|---|---|
| `capabilities/*/tests/` | **Unit tests** — package-internal, fast, no external services | Single capability |
| `platform/tests/integration/` | **Integration tests** — cross-capability, require running services | Multiple capabilities |
| `platform/tests/e2e/` | **End-to-end tests** — full system, user-facing workflows | Entire platform |
| `platform/tests/perf/` | **Performance tests** — load, stress, benchmarks | Entire platform |
| `platform/tests/security/` | **Security tests** — SAST, DAST, dependency scanning | Entire platform |

**Rule:** integration tests never live inside a capability. They live in `platform/tests/` and reference capabilities by name.

---

## 6. Migration from current state

### Phase 1: Create new structure
1. Create `capabilities/workflow-runner/` from `agentic/src/workflow-runner/`
2. Create `capabilities/control-center-ui/` from `agentic/src/control-center-ui/`
3. Create `capabilities/langgraph/` from `agents/langgraph/`
4. Create `capabilities/opencode/` from `agents/opencode/`
5. Create `capabilities/autogen/` from `agents/autogen/`
6. Add `package.yaml` to each
7. Reconcile any code differences between `agents/` and `agentic/src/` (they may be duplicates)

### Phase 2: Update delivery engine
1. Rewrite `delivery/commands/test.py` to discover `package.yaml` files
2. Rewrite `delivery/commands/build.py` to use `package.yaml` build commands
3. Rewrite `delivery/commands/publish.py` to use `package.yaml` docker images
4. Rewrite `delivery/commands/deploy.py` to use `package.yaml` compose files

### Phase 3: Update workflows
1. `.gitea/workflows/main.yml` becomes generic:
   - discover packages
   - build changed packages
   - run tests per package manifest
   - deploy to environment

### Phase 4: Cleanup
1. Remove `agents/` (after verifying nothing is needed)
2. Remove `agentic/src/` (after migration)
3. Update `docs/target-state.md`

---

## 7. Trade-offs and considerations

### Pro: Future-proof
Adding a Go or Rust capability requires only:
1. A new directory under `capabilities/`
2. A `package.yaml` with `type: go` or `type: rust`
3. A build command

The delivery engine needs no changes.

### Pro: AI-maintainable
An AI agent can:
1. Scan `capabilities/*/package.yaml`
2. Understand the full capability graph
3. Make changes to a single capability without touching others
4. Execute `delivery build <capability>` in isolation

### Con: Initial migration effort
Moving ~5 capabilities, reconciling duplicates, updating the delivery engine, and updating workflows is a medium-sized refactor.

### Con: package.yaml duplication
Some metadata exists in both `package.yaml` and language-specific files. This is intentional — `package.yaml` is for the delivery engine, `pyproject.toml`/`package.json` are for language tooling.

---

## 8. Example: Future Go capability

```
capabilities/scheduler/
  package.yaml          # type: go, build/test commands
  go.mod
  main.go
  tests/
  Dockerfile
  README.md
```

The delivery engine reads `package.yaml`, sees `type: go`, executes the declared build/test commands. No engine changes needed.

---

## Decision needed

Do you want me to:
1. **Implement this plan now** (restructure into `capabilities/`, rewrite delivery engine)
2. **Refine the plan first** (adjust names, add/remove sections, change conventions)
3. **Do a partial migration** (keep `agentic/src/` but add `package.yaml` files and update the delivery engine to use them)
