# Package-Based Delivery Architecture

## Core principle

The repository is a **registry of deployable packages**. Each package is independently buildable, testable, and deployable using its native tooling. The delivery system is a thin orchestrator that discovers packages, resolves providers, and executes declared contracts.

Capabilities are **metadata inside a package** (`provides:`), not the organizing principle. One package can implement many capabilities; one capability can span multiple packages.

---

## 1. Why packages, not capabilities, as the top-level organization

| Approach | Pro | Con |
|---|---|---|
| `capabilities/` | Matches architectural vocabulary | Conflates deployable units with logical features; one service often implements many capabilities |
| `packages/` | Matches deployment/build reality; one package = one build/test/deploy unit | Less obviously "business-focused" |
| `services/` | Clear runtime intent | Implies only runtime services, not libraries/tools |
| `modules/` | Language-neutral | Vague; doesn't imply deployability |

**Decision: `packages/`**

Reasoning:
- The delivery system builds, tests, and deploys **units of deployment**, not conceptual capabilities.
- A single package (e.g., `workflow-runner`) may provide capabilities like `workflow-execution`, `step-execution`, and `state-management`.
- A capability like `authentication` may span multiple packages (`control-center-ui`, `workflow-runner`, `langgraph`).
- Organizing by package makes the delivery system trivial: discover directories, read manifests, invoke providers.
- Organizing by capability would require the delivery system to understand cross-cutting concerns, which adds complexity for no benefit.

---

## 2. Repository layout

```
packages/
  workflow-runner/
    package.yaml
    pyproject.toml
    src/
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
    src/
    tests/
    Dockerfile
    README.md

  opencode/
    package.yaml
    pyproject.toml
    src/
    tests/
    Dockerfile
    README.md

  autogen/
    package.yaml
    pyproject.toml
    src/
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
  package_registry/
  provider_registry/
  providers/
    python.py
    typescript.py
    go.py
    rust.py
  engine.py
  cli.py

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

**Why `packages/` at the root?**
- Clear, discoverable, and language-neutral.
- One level of nesting: `packages/<name>/` — easy to glob, easy to scan.
- No ambiguity about what's a package vs. platform-level code.

**Why `platform/tests/` for integration tests?**
- Integration tests are cross-cutting by definition. They don't belong to a single package.
- Keeping them in `platform/` makes it obvious they test the platform, not an individual package.
- Future test types (perf, security, chaos) also live here.

---

## 3. Package metadata (package.yaml)

Every package declares itself with a **declarative manifest**. The delivery engine reads this metadata and invokes the appropriate provider. No shell commands in YAML.

```yaml
# packages/workflow-runner/package.yaml
name: workflow-runner
version: 0.1.0
description: Workflow runner service

kind: service
type: python

provides:
  - workflow-execution
  - step-execution
  - state-management

deployable: true
dockerfile: Dockerfile

# Dependencies (for future dependency graph support)
depends_on:
  - postgres
  - redis

build_dependencies: []
runtime_dependencies:
  - postgres
  - redis

tags:
  - backend
  - core
```

```yaml
# packages/control-center-ui/package.yaml
name: control-center-ui
version: 0.1.0
description: Control center web UI

kind: service
type: typescript

provides:
  - web-ui
  - workflow-visualization

deployable: true
dockerfile: Dockerfile

depends_on: []
build_dependencies: []
runtime_dependencies: []

tags:
  - frontend
  - ui
```

**Design decisions:**

| Field | Purpose | Why it's here |
|---|---|---|
| `name` | Package identifier | Used by delivery engine, compose, registry |
| `version` | Semantic version | Declared by package maintainer; Git SHA used for builds |
| `kind` | `service`, `library`, `tool`, `plugin` | Determines deployability and lifecycle |
| `type` | `python`, `typescript`, `go`, `rust` | Selects the provider |
| `provides` | Capability list | Metadata for humans and AI agents; not enforced by delivery engine |
| `deployable` | Boolean | Whether this package produces a runtime artifact |
| `dockerfile` | Path to Dockerfile | Convention: defaults to `Dockerfile` if omitted |
| `depends_on` | Package dependencies | For future dependency graph resolution |
| `build_dependencies` | Build-time deps | Separate from runtime; used for incremental builds |
| `runtime_dependencies` | Runtime deps | Used for compose dependencies, health checks |
| `tags` | Filtering labels | For selective builds, environment-specific deployments |

**Why no shell commands in `package.yaml`?**
- `package.yaml` is stable metadata. Build commands change when tooling changes; metadata shouldn't.
- Providers encapsulate build logic. Adding a new language means implementing a new provider, not editing every `package.yaml`.
- The delivery engine stays small: it orchestrates, it doesn't script.

**Why not derive everything from Git?**
- `version` is semantic, not derived from Git. Git provides the build SHA (`${GIT_SHA}`).
- `name`, `type`, `kind`, `provides` are architectural decisions, not derivable from filesystem structure.
- `dockerfile` path is a convention, but explicit is better than implicit.

---

## 4. Language providers

Providers encapsulate all language-specific knowledge. The delivery engine never needs to know about Python, TypeScript, Go, or Rust.

### Provider interface

```python
class Provider:
    def discover(self, package_path: Path) -> dict:
        """Scan package directory and return source/test locations."""

    def build(self, package_path: Path, context: BuildContext) -> BuildResult:
        """Execute language-specific build."""

    def test(self, package_path: Path, context: TestContext) -> TestResult:
        """Execute language-specific tests."""

    def publish(self, package_path: Path, context: PublishContext) -> PublishResult:
        """Produce publishable artifact (image, binary, etc.)."""

    def package(self, package_path: Path, context: PackageContext) -> PackageResult:
        """Create distributable package."""
```

### Example providers

**PythonProvider:**
- `discover`: find `src/` and `tests/` directories, read `pyproject.toml`
- `build`: `pip install -e .` or `python -m build`
- `test`: `pytest tests/ -v`
- `publish`: `docker build` using package's Dockerfile
- `package`: wheel/sdist

**TypeScriptProvider:**
- `discover`: find `src/` and `tests/` directories, read `package.json`
- `build`: `npm run build` or `tsc`
- `test`: `vitest run tests/unit` and `vitest run tests/e2e`
- `publish`: `docker build` using package's Dockerfile
- `package`: npm package or Docker image

**GoProvider:**
- `discover`: find `*.go` files, read `go.mod`
- `build`: `go build ./...`
- `test`: `go test ./...`
- `publish`: `docker build` using package's Dockerfile
- `package`: Go binary

**Adding a new language:**
1. Implement `Provider` interface
2. Register in `provider_registry/`
3. No changes to delivery engine, no changes to `package.yaml` schema

---

## 5. Delivery engine architecture

The delivery engine has three separate components:

### 5.1 Package Registry

Responsible for discovering and indexing packages.

```python
class PackageRegistry:
    def discover(self, root: Path = Path("packages")) -> list[Package]:
        """Scan packages/*/package.yaml and return indexed packages."""

    def get(self, name: str) -> Package | None:
        """Look up a specific package."""

    def list(self, kind: str | None = None, tags: list[str] | None = None) -> list[Package]:
        """List packages, optionally filtered."""
```

**Responsibilities:**
- Scan filesystem for `package.yaml` files
- Parse and validate manifests
- Index by name, kind, type, tags
- Detect changes (future: map git diff to packages)

### 5.2 Provider Registry

Responsible for selecting the right provider for a package.

```python
class ProviderRegistry:
    def register(self, type: str, provider: Provider) -> None:
        """Register a provider for a package type."""

    def resolve(self, package: Package) -> Provider:
        """Return the provider for a package's type."""
```

**Responsibilities:**
- Map `type` → `Provider` implementation
- Allow runtime registration of new providers
- Fallback/default provider handling

### 5.3 Execution Engine

Responsible for orchestrating build, test, publish, and deploy workflows.

```python
class ExecutionEngine:
    def __init__(self, package_registry: PackageRegistry, provider_registry: ProviderRegistry):
        ...

    def build(self, packages: list[str], changed_only: bool = False) -> BuildResult:
        """Build specified packages."""

    def test(self, packages: list[str], kind: str = "unit") -> TestResult:
        """Run tests for specified packages."""

    def publish(self, packages: list[str]) -> PublishResult:
        """Publish packages to registry."""

    def deploy(self, environment: str, packages: list[str]) -> DeployResult:
        """Deploy packages to environment."""

    def validate(self, environment: str) -> ValidationResult:
        """Validate deployment."""
```

**Responsibilities:**
- Orchestrate package lifecycle
- Invoke providers in correct order
- Handle errors, retries, rollbacks
- Emit events/logs for observability
- **Never** know about Python, TypeScript, Go, etc. — that's the provider's job

---

## 6. Data flow

```
Repository
    ↓
Package Registry
    ↓ scan packages/*/package.yaml
    ↓ index by name, type, kind
    ↓
Provider Registry
    ↓ resolve type → Provider
    ↓
Execution Engine
    ↓
Dependency Graph (future)
    ↓ resolve build_dependencies / runtime_dependencies
    ↓
Build
    ↓ provider.build() for each package
    ↓ docker build / pip install / npm build / go build
    ↓
Registry
    ↓ tag with ${REGISTRY}/${name}:${GIT_SHA}
    ↓ push
    ↓
Deployment
    ↓ provider.publish()
    ↓ docker compose up -d
    ↓
Validation
    ↓ health checks, smoke tests
    ↓
Promotion
    ↓ promote dev → live
    ↓
Runtime
```

**Key insight:** The delivery engine is a generic orchestrator. All language-specific behavior lives in providers. All package-specific metadata lives in `package.yaml`. The engine never needs to change when a new language or package type is added.

---

## 7. Test separation

| Directory | Purpose | Scope | Owner |
|---|---|---|---|
| `packages/*/tests/` | **Unit tests** — package-internal, fast, no external services | Single package | Package maintainer |
| `platform/tests/integration/` | **Integration tests** — cross-capability, require running services | Multiple packages | Platform team |
| `platform/tests/e2e/` | **End-to-end tests** — full system, user-facing workflows | Entire platform | Platform team |
| `platform/tests/perf/` | **Performance tests** — load, stress, benchmarks | Entire platform | Platform team |
| `platform/tests/security/` | **Security tests** — SAST, DAST, dependency scanning | Entire platform | Platform team |

**Rule:** package-local tests never test cross-cutting concerns. Integration tests never live inside a package.

---

## 8. Package independence

Every package is independently buildable and testable using its native tooling:

```bash
cd packages/workflow-runner
pytest tests/ -v
python -m build

cd packages/control-center-ui
vitest run tests/unit
npm run build
```

The `delivery` CLI is just an orchestrator. Developers can work inside a single package without understanding the rest of the repo or the delivery engine internals.

---

## 9. Migration from current state

### Phase 1: Restructure directories
1. Create `packages/workflow-runner/` from `agentic/src/workflow-runner/`
2. Create `packages/control-center-ui/` from `agentic/src/control-center-ui/`
3. Create `packages/langgraph/` from `agents/langgraph/`
4. Create `packages/opencode/` from `agents/opencode/`
5. Create `packages/autogen/` from `agents/autogen/`
6. Reconcile any code differences between `agents/` and `agentic/src/`
7. Add `package.yaml` to each package
8. Create `platform/tests/` directories

### Phase 2: Implement delivery engine
1. Create `delivery/package_registry/` — filesystem scanner, manifest parser, indexer
2. Create `delivery/provider_registry/` — type → provider mapping
3. Create `delivery/providers/python.py` — PythonProvider implementation
4. Create `delivery/providers/typescript.py` — TypeScriptProvider implementation
5. Create `delivery/engine.py` — orchestrator
6. Create `delivery/cli.py` — Typer CLI

### Phase 3: Update workflows
1. `.gitea/workflows/main.yml` becomes generic:
   - `delivery discover`
   - `delivery build --all`
   - `delivery test unit`
   - `delivery test integration`
   - `delivery deploy dev`
   - `delivery validate dev`

### Phase 4: Cleanup
1. Remove `agents/` (after verifying nothing is needed)
2. Remove `agentic/src/` (after migration)
3. Update `docs/target-state.md`

---

## 10. Trade-offs and considerations

### Pro: Future-proof
Adding a Go, Rust, or any other language package requires only:
1. A new directory under `packages/`
2. A `package.yaml` with appropriate metadata
3. A new provider implementation

The delivery engine and existing providers need no changes.

### Pro: AI-maintainable
An AI agent can:
1. Scan `packages/*/package.yaml`
2. Understand the full package graph
3. Make changes to a single package without touching others
4. Execute `delivery build <package>` in isolation
5. Understand capabilities by reading the `provides` field

### Pro: Fast iteration
Developers can:
1. Work inside a single package directory
2. Run tests with native tooling (`pytest`, `vitest`, `go test`)
3. Build with `docker build` using the package's Dockerfile
4. Deploy with `delivery deploy <package>`

### Pro: Clean separation of concerns
- Package metadata: declarative, stable, language-neutral
- Providers: language-specific behavior, encapsulated
- Delivery engine: thin orchestrator, never needs to know about languages

### Con: Initial migration effort
Moving ~5 packages, reconciling duplicates, implementing providers, and updating workflows is a medium-sized refactor.

### Con: package.yaml is declarative only
Some teams prefer having build commands in metadata for quick edits. This design requires implementing a provider for any build/test customization. Trade-off: more upfront work, but much more maintainable long-term.

### Con: Provider interface must be well-designed
If the provider interface is too narrow, future languages won't fit. If too broad, providers become complex. The interface above is a starting point; it can evolve as new languages are added.

---

## 11. Example: Future Go capability

```
packages/scheduler/
  package.yaml          # type: go, kind: service, provides: [job-scheduling]
  go.mod
  main.go
  tests/
  Dockerfile
  README.md
```

The delivery engine:
1. Discovers `packages/scheduler/package.yaml`
2. Resolves `type: go` → `GoProvider`
3. Invokes `GoProvider.build()`, `GoProvider.test()`, etc.
4. No engine changes needed.

---

## 12. Decision needed

Do you want me to:
1. **Implement this plan now** (restructure into `packages/`, add `package.yaml` files, implement delivery engine with providers)
2. **Refine the plan first** (adjust names, add/remove sections, change provider interface, adjust metadata fields)
3. **Do a partial migration** (keep current layout but add `package.yaml` files and implement the delivery engine)
