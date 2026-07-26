# Configuration Manager Capability — Implementation Plan (Final)

## Objective

Prove the end-to-end flow:

```
.env -> Provider -> ConfigurationManager -> immutable typed model -> constructor injection
```

Phase 1 is deliberately minimal. Future architecture is not built before the first capability works.

---

## 1. Repository Analysis

- `os.getenv()` used in 12 sites across 5 files in `packages/`
- `packages/workflow-runner/api.py` is the service entry point; it creates `EventBus()` and `_build_scheduler()` lazily — both rely on env config
- `packages/workflow-runner/db.py`, `runtime_client.py`, `scheduler.py` read env directly via module-level constants
- `packages/bus/src/bus.py` duplicates `EventBus` with identical `os.getenv` pattern
- No shared config module; each package reads its own env vars independently
- Defaults (`os.getenv("X", "default")`) hide missing configuration until runtime — violates PAT-013

---

## 2. Architectural Principles

### 2.1 Resolution mechanics, not capability ownership

The `configuration` package owns resolution mechanics (providers, manager, validation). Configuration models are migration scaffolding. Future capability-specific configuration models must be able to live alongside their capability, not in the `configuration` package.

**Dependency direction:**

Capabilities own their configuration models:

```
Capability A
     |
     v
Configuration Model A

Capability B
     |
     v
Configuration Model B
```

The `ConfigurationManager` is a mechanism that operates on models supplied by the caller:

```
Composition Root
     |
     | supplies model class
     v
ConfigurationManager.resolve(ModelClass)
     |
     | uses
     v
Provider
```

The manager is not below capabilities. It does not own or import configuration models.

**Hard rules:**
- ConfigurationManager must NOT import concrete configuration models.
- Providers must NOT know concrete configuration models.
- The manager only accepts model classes dynamically via `resolve(ModelClass)`.

**Temporary scaffolding note:** The `contracts/` directory exists only as a temporary migration location because no capability-specific configuration package exists yet. It must not become a registry of all application configuration. New capabilities introduced after Phase 1 should place configuration models beside the owning capability (e.g. `packages/workflow-runner/configuration/database.py`).

Phase 1 temporarily contains models in `packages/configuration/contracts/v1/`, but the code structure must allow moving:

Before: `packages/configuration/contracts/v1/database.py`
After: `packages/workflow-runner/configuration/database.py`

without changing `ConfigurationManager`.

### 2.2 Composition root only (PAT-018)

`ConfigurationManager` is a composition-root abstraction. It is never injected into services. Services receive immutable typed configuration objects.

Only application startup code may:
- create `ConfigurationManager`
- select providers
- resolve configuration
- construct services

Everything below startup receives already-resolved dependencies.

### 2.3 Provider responsibility separation

- **Providers** resolve raw values from sources (env, files, secrets stores). They raise `ProviderUnavailableError` if the source is unavailable.
- **Configuration models** declare required keys and types using Pydantic `Field(validation_alias=...)`.
- **ConfigurationManager** takes raw values from provider, builds the model, catches validation failures, and raises `ConfigurationResolutionFailed`.

Providers do not contain knowledge of every configuration model.

### 2.4 Immutable configuration

Configuration is resolved once during bootstrap and treated as immutable for the application lifetime. `resolve()` caches results. Services receive frozen configuration objects.

### 2.5 Dependency inversion — constructor injection only

Components receive resolved typed configuration objects through constructors. Never inject primitives (strings, ints, dicts) that leak hidden contracts.

**Rule: Services receive configuration objects. Low-level infrastructure adapters receive explicit constructor arguments derived from configuration objects.**

```python
# api.py bootstrap (composition root)
manager = ConfigurationManager(DotEnvProvider())
bus_cfg = manager.resolve(MessageBusConfiguration)
db_cfg = manager.resolve(DatabaseConfiguration)

# Services receive configuration objects
scheduler = build_scheduler(database=db_cfg)

# Low-level adapters receive explicit arguments derived from config
# This keeps the bus package independent of the configuration package
event_bus = EventBus(url=bus_cfg.url, fallback_dir=bus_cfg.fallback_dir)
```

No service locator, no global container, no DI framework.

### 2.6 Environment isolation and dependency direction

Only the `configuration` capability may access:
- `os.environ`
- `dotenv`
- secret stores

No other application package may directly load environment variables.

**Allowed locations for env access:**
- `packages/configuration/**`
- Composition-root files: `packages/*/api.py`, `packages/*/main.py`, `packages/*/startup.py`, `packages/*/bootstrap.py`

**Forbidden locations for env access:**
- `services/`
- `workers/`
- `handlers/`
- `tasks/`
- domain logic
- libraries

The `configuration` package must NOT import:
- `EventBus` / `aiassistant-bus`
- `workflow-runner` or any capability package
- service locators or registries

Dependency direction:
```
workflow-runner  --->  configuration
bus              --->  configuration
```

NOT:
```
configuration  --->  bus
configuration  --->  workflow-runner
```

---

## 3. Phase 1 Scope

### Create: `packages/configuration/`

```
src/configuration/
    __init__.py
    contracts/
        __init__.py              # re-exports only; no shared base class
        v1/
            __init__.py
            message_bus.py       # MessageBusConfiguration (frozen Pydantic model)
            database.py          # DatabaseConfiguration (frozen Pydantic model)
            langgraph_runtime.py # LangGraphRuntimeConfiguration (frozen Pydantic model)
    providers/
        __init__.py              # ConfigurationProvider interface, ProviderUnavailableError, ConfigurationResolutionFailed
        dotenv.py                # DotEnvProvider
    manager.py                   # ConfigurationManager (resolve with caching)
tests/
    conftest.py
    test_contracts.py
    test_providers.py
    test_manager.py
    test_fake_provider.py        # proves provider abstraction
```

### Do NOT create in Phase 1
- `capability.yaml` / metadata registry
- events module
- `runtime/` or `resolver/` subpackages
- `ProviderChain`, provider priorities, provider selection logic
- `ConfigurationContract` ABC or `FieldSpec` abstraction
- version compatibility registry
- `ConfigurationContext` (documented for future, not implemented)
- DI framework or service locator

---

## 4. Configuration Models (Contracts)

Typed Pydantic models, frozen (immutable). No common base class.

Implementation:
```python
class DatabaseConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(validation_alias="DATABASE_URL")
    pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")
```

`populate_by_name=True` is required so Pydantic v2 accepts raw dict keys like `DATABASE_URL` when building the model via `model_validate()`. Do not rely on implicit behaviour.

Explicit mapping via `validation_alias` + `populate_by_name=True`. No hidden magic. The contract declares what it needs and how external names map to fields.

**`MessageBusConfiguration`**
- `url: str` = Field(validation_alias="RABBITMQ_URL")
- `fallback_dir: str` = Field(default="/aiassistant/.events", validation_alias="EVENTS_FALLBACK_DIR")

**`DatabaseConfiguration`**
- `url: str` = Field(validation_alias="DATABASE_URL")
- `pool_size: int` = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
- `max_overflow: int` = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")

**`LangGraphRuntimeConfiguration`**
- `url: str` = Field(default="http://langgraph:8000", validation_alias="LANGGRAPH_URL")
- `timeout_seconds: float` = Field(default=300.0, validation_alias="LANGGRAPH_TIMEOUT")
- `retries: int` = Field(default=3, validation_alias="LANGGRAPH_RETRIES")

These models are temporary migration scaffolding for Phase 1.

> **Ownership note:** These models live in `packages/configuration/contracts/` only because no capability-specific configuration package exists yet. The `ConfigurationManager` must remain independent of model location. Future capabilities may own their own configuration models (e.g. `packages/workflow-runner/configuration/database.py`). Do not treat this folder as the permanent home of every configuration contract. New capabilities introduced after Phase 1 should place configuration models beside the owning capability.

In future, capability-specific configuration models will live alongside their capability. The `configuration` package provides the resolution mechanism, not ownership of all configuration definitions.

---

## 5. Provider Interface

Providers resolve raw values. They do not know about configuration models.

```python
class ProviderUnavailableError(Exception):
    """Raised when a configuration source is unavailable."""

class ConfigurationProvider:
    name: str

    def read(self) -> dict[str, str]:
        """Read raw values from the source. Returns a flat dict of string key-value pairs.
        Raises ProviderUnavailableError if the source is unavailable."""
```

Single implementation: `DotEnvProvider`. Reads `.env` / `os.environ` and returns a flat dict of string values.

No `ProviderChain`. No priorities. One provider for now.

---

## 6. ConfigurationManager

```python
class ConfigurationManager:
    def __init__(self, provider: ConfigurationProvider) -> None: ...

    def resolve(self, model_cls: type[T]) -> T:
        """Resolve a configuration model via the provider.
        Reads raw values from provider, validates against model, caches result.
        Raises ConfigurationResolutionFailed if required fields are missing or validation fails."""
```

Responsibilities:
1. Ask provider for raw values (`provider.read()`)
2. Create validated model instance (`model_cls.model_validate(raw_values)`)
3. Cache result for application lifetime in `dict[type[BaseModel], BaseModel]`
4. Raise `ConfigurationResolutionFailed` with diagnostic message if validation fails

Important: ConfigurationManager does NOT import concrete configuration models. It accepts model classes dynamically via the `model_cls` parameter.

Cache: `dict[type[BaseModel], BaseModel]` — keyed by model class, not by string. Avoids collisions and preserves type safety. Cached objects are immutable frozen Pydantic models, so sharing instances between consumers is safe.

Cache lifetime: ConfigurationManager instance lifetime = application startup lifetime. No global cache, no singleton, no distributed cache.

---

## 7. Bootstrap Lifecycle

```
1. manager = ConfigurationManager(DotEnvProvider())
2. bus_cfg = manager.resolve(MessageBusConfiguration)      # cached
3. db_cfg = manager.resolve(DatabaseConfiguration)         # cached
4. langgraph_cfg = manager.resolve(LangGraphRuntimeConfiguration)  # cached
5. event_bus = EventBus(url=bus_cfg.url, fallback_dir=bus_cfg.fallback_dir)  # low-level adapter gets explicit args
6. scheduler = build_scheduler(database=db_cfg)            # service gets config object
7. Start event bus consumers
```

Configuration is resolved once at bootstrap and cached. Subsequent `resolve()` calls for the same model return the cached instance.

The manager is not a service. It is a bootstrap object.

---

## 8. Constructor Injection Rule

Components receive configuration objects, not primitive values.

```python
# Services receive configuration objects
build_scheduler(database: DatabaseConfiguration)

# Low-level infrastructure adapters receive explicit arguments derived from configuration
event_bus = EventBus(url=bus_cfg.url, fallback_dir=bus_cfg.fallback_dir)

# Incorrect: primitives leak hidden contracts
build_scheduler(database_url: str)

# Incorrect: infrastructure adapter becomes configuration-aware
event_bus = EventBus(configuration=bus_cfg)  # couples bus package to configuration package
```

---

## 9. Future Extension Points (Documented Only)

Provider implementations can later include:
- `DotEnvProvider` (existing)
- `EnvironmentProvider` (direct `os.environ`)
- `VaultProvider`
- `KubernetesSecretsProvider`
- `GeneratedCredentialProvider`
- `CloudSecretManagerProvider`

`ConfigurationContext` (not implemented in Phase 1):
```python
class ConfigurationContext:
    environment: str  # "dev" | "live" | "test"
```

Providers may later use this context to determine where configuration comes from.

---

## 10. workflow-runner Migration — First Consumer

### Files modified

- **`packages/workflow-runner/api.py`**
  - Bootstrap section creates `ConfigurationManager(DotEnvProvider())`
  - Resolves `MessageBusConfiguration`, `DatabaseConfiguration`, `LangGraphRuntimeConfiguration`
  - Injects into `_bus()` and `_scheduler()` factory functions as configuration objects
  - Removes reliance on module-level `os.getenv` defaults

- **`packages/workflow-runner/db.py`**
  - Constructor accepts `database: DatabaseConfiguration`
  - Removes module-level `DATABASE_URL = os.getenv(...)`

- **`packages/workflow-runner/scheduler.py`**
  - `_build_scheduler()` accepts `database: DatabaseConfiguration`
  - Removes `os.getenv` fallback (parameter is already partially supported)

- **`packages/workflow-runner/runtime_client.py`**
  - Constructor accepts `langgraph: LangGraphRuntimeConfiguration`
  - Removes module-level `LANGGRAPH_URL`, `LANGGRAPH_TIMEOUT`, `LANGGRAPH_RETRIES` constants

- **`packages/bus/src/bus.py`** and **`packages/workflow-runner/bus.py`**
  - `EventBus.__init__()` requires `url: str` and `fallback_dir: str` as parameters (remove defaults that call `os.getenv`)
  - The composition root derives these from `MessageBusConfiguration` and passes them explicitly
  - This keeps the `bus` package independent of the `configuration` package

### Note on WorkflowRunner class

There is no `WorkflowRunner` class in this codebase. The service entry point is `api.py`. The objects that consume configuration are `EventBus` and `_build_scheduler()`.

---

## 11. File-by-file Action List

### CREATE
- `packages/configuration/pyproject.toml`
- `packages/configuration/src/configuration/__init__.py`
- `packages/configuration/src/configuration/contracts/__init__.py`
- `packages/configuration/src/configuration/contracts/v1/__init__.py`
- `packages/configuration/src/configuration/contracts/v1/message_bus.py`
- `packages/configuration/src/configuration/contracts/v1/database.py`
- `packages/configuration/src/configuration/contracts/v1/langgraph_runtime.py`
- `packages/configuration/src/configuration/providers/__init__.py`
- `packages/configuration/src/configuration/providers/dotenv.py`
- `packages/configuration/src/configuration/manager.py`
- `packages/configuration/tests/conftest.py`
- `packages/configuration/tests/test_contracts.py`
- `packages/configuration/tests/test_providers.py`
- `packages/configuration/tests/test_manager.py`
- `packages/configuration/tests/test_fake_provider.py`

### MODIFY
- `packages/workflow-runner/api.py`
- `packages/workflow-runner/db.py`
- `packages/workflow-runner/scheduler.py`
- `packages/workflow-runner/runtime_client.py`
- `packages/bus/src/bus.py`
- `packages/workflow-runner/bus.py`

---

## 12. Test Strategy

### Unit tests (new)
- `test_contracts.py` — Pydantic validation, required fields, defaults, immutability (mutation raises), `validation_alias` mapping, alias-based population from provider-shaped dicts
- `test_providers.py` — DotEnvProvider reads env vars, returns flat dict, raises `ProviderUnavailableError` when source unavailable
- `test_manager.py` — resolve() returns cached model; raises `ConfigurationResolutionFailed` with diagnostic message on missing required fields; importing `configuration.manager` does not import capability packages
- `test_fake_provider.py` — FakeProvider + ConfigurationManager proves consumers behave identically regardless of provider. **Must not instantiate DotEnvProvider.** The purpose is to prove provider substitution works without relying on the real provider.

### Integration test
- `test_workflow_runner_migration.py` — construct manager, resolve all 3 models, call modified constructors with injected values, assert no `os.getenv` in consumer path

### Repository-wide validation sweeps (safety checks)

Before deleting env access from migrated files:
- Grep all packages excluding `packages/configuration/` for `os.getenv`, `os.environ`, `dotenv`, `load_dotenv`
- Confirm zero matches after migration

After migration:
- Grep all packages excluding `packages/configuration/` and composition-root files (`api.py`, `main.py`, `startup.py`, `bootstrap.py`) for `ConfigurationManager(`
- Confirm zero matches — `ConfigurationManager` must not appear inside services, workers, handlers, or tasks
- This is a gate before removing env access from migrated files

### Architecture boundary test
- Importing `configuration.manager` must not import `workflow_runner`, `bus`, or any capability package
- Verify by checking `sys.modules` after import or by grepping for capability imports in `manager.py`

---

## 13. Migration Sequence

Implement in this order to reduce blast radius:

**Step 1: Create configuration package**
- Create `packages/configuration/` with contracts, providers, manager, tests
- Validation: `pytest packages/configuration/tests/` passes

**Step 2: Migrate EventBus**
- Update `packages/bus/src/bus.py` and `packages/workflow-runner/bus.py` to require `url` and `fallback_dir` as constructor parameters (remove `os.getenv` defaults)
- Validation: EventBus has zero environment access

**Step 3: Migrate workflow-runner components**
Order:
1. `db.py` — accept `DatabaseConfiguration`, remove `os.getenv`
2. `scheduler.py` — accept `DatabaseConfiguration`, remove `os.getenv`
3. `runtime_client.py` — accept `LangGraphRuntimeConfiguration`, remove `os.getenv`
4. `api.py` — bootstrap with `ConfigurationManager`, resolve contracts, inject into `_bus()` and `_scheduler()`

Validation after each file: targeted test passes, no `os.getenv` in migrated file

**Step 4: Repository sweep**
- Grep all packages excluding `packages/configuration/` for `os.getenv`, `os.environ`, `dotenv`, `load_dotenv`
- Grep for `ConfigurationManager(` outside composition-root files
- Confirm zero matches

---

## 14. Acceptance Criteria

- [ ] `pytest packages/configuration/tests/` passes
- [ ] `pytest packages/workflow-runner/tests/` still passes after migration
- [ ] `ConfigurationManager` imports no concrete capability models
- [ ] `DotEnvProvider` imports no concrete capability models
- [ ] `resolve()` accepts any Pydantic model class dynamically
- [ ] Consumers receive configuration objects, not primitives
- [ ] `EventBus` constructor requires explicit `url: str` and `fallback_dir: str` (derived from configuration object at composition root)
- [ ] `build_scheduler` constructor accepts `database: DatabaseConfiguration` (not `database_url: str`)
- [ ] `FakeProvider` test proves provider independence — consumers behave identically with fake vs dotenv provider (test must not instantiate DotEnvProvider)
- [ ] Configuration models are frozen/immutable — mutation raises
- [ ] `resolve()` caches results — second call returns same instance (cache keyed by model class)
- [ ] Cached configuration objects are immutable and safe to share between consumers
- [ ] Alias-based population: `model_validate({"DATABASE_URL": "postgres://...", "DATABASE_POOL_SIZE": "10"})` correctly populates `DatabaseConfiguration` with coerced types
- [ ] Importing `configuration.manager` does not import `workflow_runner`, `bus`, or any capability package
- [ ] Configuration models can be moved to a capability package without modifying `ConfigurationManager`
- [ ] No `os.getenv` remains in `packages/workflow-runner/db.py`, `scheduler.py`, or `runtime_client.py`
- [ ] Missing `DATABASE_URL` env var → startup fails with `ConfigurationResolutionFailed` (not later, not silently)
- [ ] Workflow-runner runs end-to-end with injected contracts (manual smoke test)
- [ ] **No consumer package imports `dotenv` or accesses environment variables directly** (repo-wide grep, excluding `packages/configuration/`)
- [ ] **`ConfigurationManager(` does not appear inside services, workers, handlers, or tasks** (repo-wide grep, excluding composition-root files)

---

## 14. Risks

| Risk | Mitigation |
|---|---|
| Circular dep: configuration → bus | Phase 1 has zero dependency on bus package |
| DotEnvProvider becomes architecture | It is initial provider only; consumers depend on models, not the provider |
| Breaking existing consumers | Migrate workflow-runner first; validate before expanding |
| Defaults hiding missing config | Required fields without env vars raise `ConfigurationResolutionFailed` at startup |
| Secret exposure in logs | `DatabaseConfiguration.url` carries sensitive data; manager and consumers must not log model values |
| Coupling via model location | ConfigurationManager accepts model classes dynamically; models can move to capabilities without changing manager |

---

## 15. Out of Scope (Phase 2+)

- Event publishing from ConfigurationManager
- Capability discovery metadata (`capability.yaml`)
- Version compatibility checks between contract versions
- `ProviderChain`, provider priorities, provider selection logic
- Additional providers (Vault, Kubernetes secrets, cloud secret managers)
- Migration of `packages/capability_registry/`, `packages/ai/`
- Distributed configuration service
- `ConfigurationContext` for environment-aware resolution
- DI framework or service locator

---

## 16. Post-Implementation Documentation (After Code Works)

Once the implementation is validated, create:

- `docs/architecture/patterns/PAT-018-composition-root.md` — documents the pattern proven by this implementation: only startup code creates the `ConfigurationManager`, selects providers, resolves configuration, and constructs services.
- `docs/architecture/patterns/PAT-019-configuration-resolution.md` — documents the resolution pattern: provider returns raw values, manager validates against frozen Pydantic models, result is cached and injected via constructors.

The code establishes the pattern first. The documentation describes the proven pattern second.

---

## 17. Overall Architecture (Reference)

```
                 Composition Root
                       |
                       |
              ConfigurationManager
                       |
                       |
                 ConfigurationProvider
                       |
                       |
              Immutable Configuration Model
                       |
                       |
              Constructor Injection
                       |
                       |
                  Application Service
```

The goal of Phase 1 is not to build a complete configuration platform. The goal is to establish the dependency inversion boundary that allows future providers (dotenv, Kubernetes Secrets, Vault, cloud secret managers, generated credentials, agent-managed credentials) without changing application code.
