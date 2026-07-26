# Capability Bootstrapper Implementation Plan (Implementation Ready)

## Context
We are migrating from self‑bootstrapping capabilities to a platform‑hosted model. The platform owns lifecycle and dependency provision; capabilities own business behavior and contracts.

## Core Objective
Prove that **one** capability (the CI Worker) can be **hosted** by platform infrastructure, receive all required dependencies, start, run and stop, **without knowing how the platform provided anything**.

---

# Architecture Rules

## Platform Owns Orchestration
The platform bootstrapper owns:
- Lifecycle management  
- Configuration resolution
- Platform service creation (logger, event‑bus)  
- Capability construction  
- Startup sequencing  

Capabilities own:
- Business behavior
- Domain contracts
- Their **own** configuration contracts
- Capability events

Capabilities **MUST NOT**:
- Create `ConfigurationManager`
- Select configuration providers
- Read environment variables
- Load `.env` files
- Initialize infrastructure services (logging, bus, etc.)

---

## Dependency Direction
```
Platform Bootstrapper
        ↓
Capability Contract
        ↓
Capability Implementation
```
**Forbidden:** Capability → Platform infrastructure (e.g., `ConfigurationManager`)

---

# Phase 1 Scope (Minimal)
**Implement ONLY:**
- Capability lifecycle protocol (`Capability` protocol)
- `PlatformBootstrapper` orchestrator  
- `CapabilityContext` immutable boundary
- CI Worker migration to a hosted capability

**Do NOT implement:**
- `CapabilityFactory`
- Service Registry
- Plugin discovery
- Dynamic capability loading
- DI framework
- Generic provider marketplace

---

# Capability Contract
Define a minimal protocol that **explicitly** declares its configuration contract and expects constructor injection of context:

```python
class Capability(Protocol):
    configuration_type: type[BaseModel]

    def __init__(self, context: "CapabilityContext"):
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...
```

- `configuration_type` is a class attribute pointing to the capability’s configuration contract (e.g., `RegistryConfiguration`).
- The bootstrapper resolves this contract **dynamically** via:
  ```python
  config = manager.resolve(capability_type.configuration_type)
  ```
- **Forbidden:** Hard‑coded calls such as `manager.resolve(RegistryConfiguration)` inside the platform.

---

# Configuration Ownership
- Each capability **owns** its configuration contract (e.g., `RegistryConfiguration` lives in the CI Worker package, **not** in a shared configuration package).  
- The platform merely resolves it; it does **not** create or populate it.

---

# Capability Context
Implement an **immutable** context that carries only the **explicitly owned** platform dependencies:

```python
@dataclass(frozen=True)
class CapabilityContext:
    configuration: BaseModel   # resolved capability configuration
    logger: Logger               # platform logger
    event_bus: EventBus          # platform event bus
```

- No service‑lookup methods, dictionaries, registries, or arbitrary dependency bags.
- Only these three fields.

---

# Platform Bootstrapper Lifecycle
`bootstrap(capability_type)` performs **exactly** this sequence:

1. Create a `ConfigurationManager` with appropriate providers (e.g., `EnvironmentProvider`).  
2. Determine the configuration contract via `capability_type.configuration_type`.  
3. Resolve the configuration using `manager.resolve(capability_type.configuration_type)`.  
4. Create platform services (logger, event bus).  
5. Assemble `CapabilityContext(configuration, logger, event_bus)`.  
6. Construct the capability instance via constructor injection:  
   ```python
   capability = capability_type(context=context)
   ```
7. Call `capability.start()`.  
8. Return the started capability.

**Critical:** Any missing required configuration must cause failure **before** step 6 (during steps 1‑3). Example: missing `REGISTRY_USERNAME` fails immediately; it does **not** start the capability and then fail later.

---

# CI Worker Migration
The CI Worker is the **first hosted capability**.

**Remove from CI Worker:**
- All `ConfigurationManager` usage
- All `.env` loading
- All direct `os.getenv` / `os.environ` accesses
- All logger / event‑bus creation code

**Receive only:** a `CapabilityContext` instance via constructor injection.

**Own:** its own `RegistryConfiguration` contract.  
The role of the configuration mechanism is to **resolve** that contract; it must not be instantiated or populated by the CI Worker.

**Construction example (inside platform bootstrapper):**
```python
ctx = CapabilityContext(
    configuration=resolved_cfg,
    logger=logger,
    event_bus=event_bus,
)
ci_worker = CIWorker(context=ctx)   # constructor injection only
ci_worker.start()
```

---

# Implementation Steps

### 1. Define Capability Contract
- Create a `Capability` protocol with `configuration_type` attribute, `__init__(self, context: CapabilityContext)`, and `start()`/`stop()` methods.  
- Do **not** add an abstract base class unless strictly required.

### 2. Implement `CapabilityContext`
- Define an immutable `@dataclass(frozen=True)` with `configuration`, `logger`, `event_bus`.  
- No behavior, no lookup mechanisms.

### 3. Implement PlatformBootstrapper
- Orchestrates steps 1‑8 of the lifecycle above.  
- Dynamically resolves `capability_type.configuration_type`.  
- Injects the context into the capability constructor.  
- Fails fast on missing configuration.

### 4. Migrate CI Worker
- Place `RegistryConfiguration` inside the CI Worker package.  
- Refactor CI Worker to accept `CapabilityContext` via its constructor.  
- Remove all self‑bootstrap logic (dotenv, env var reads, logger/bus init).  
- Use only injected dependencies.

### 5. Verification & Testing
**Bootstrap Tests**
- Resolve a capability’s configuration dynamically via `manager.resolve(capability_type.configuration_type)`.  
- Ensure missing configuration causes failure **before** capability construction or `start()` call.  
- Verify valid configuration results in a started capability.

**Capability Tests**
- Confirm CI Worker functions correctly with injected `CapabilityContext`.  
- Scan CI Worker source for `dotenv` imports or direct environment‑variable accesses – they must be absent.  

**Architectural Regression Tests**
- Repository‑wide scan: **No** `ConfigurationManager`, `dotenv`, or environment‑variable usage inside any capability code.  
- Repository‑wide scan: **No** provider selection logic inside capabilities.

### 6. Documentation
Create `docs/architecture/patterns/PAT-020-platform-bootstrapper.md` and document:
- Platform‑owned lifecycle and inversion of control  
- Hosted‑capability boundaries  
- Strict dependency direction (platform → capability)  
- Ownership of configuration contracts by capabilities  
- Why the platform’s mechanisms remain generic and reusable  

---

# Success Criteria
The implementation must **prove** the statement:

> “A capability can be dropped into a host, receive everything it needs, start, run and stop without knowing how the platform provided anything.”

Once demonstrated with the CI Worker, future extensions (factory, registry, discovery, etc.) become justified. Until then, keep Phase 1 **boring** and minimal.