# Increment 16 — Investigation: Application Composition, Port Implementations, and Cross-Plane Adapters

## Objective

Investigate where the system gets assembled, whether port implementations exist,
and establish clear architectural rules for adapter ownership.

**This is an investigation only. No production code was modified.**

## 1. Composition Root

### Current State

The system has **no single, explicit composition root**. Instead, composition is
scattered across multiple locations:

| Location | What it composes | Issues |
|----------|------------------|--------|
| `workflow_runner/api.py:_get_chat_service()` | `AssistantChatService()` | Creates service with **no ports wired**; acts as lazy singleton; mixes HTTP concerns with composition |
| `workflow_runner/api.py` (module level) | `ConceptStore()` at line 755 | Direct instantiation inside request handler |
| `workflow_runner/src/mcp_server.py` (module level) | `CapabilityRegistry(ConceptStoreCapabilityRepository(...))` | Direct instantiation at import time |
| `workflow_runner/src/runtime.py` | `PatternRuntime(registry=None, bus=None)` | Defaults to creating `CapabilityRegistry()` internally |
| Test files | Various services | Expected for tests, but shows no standard composition pattern |

### `workflow_runner/api.py` as De Facto Composition Root

`_get_chat_service()` (lines 614-628) is the closest thing to a composition root
for the Assistant:

```python
def _get_chat_service() -> Any:
    global _chat_service
    if _chat_service is None:
        _script_dir = Path(__file__).resolve().parent
        _packages_root = _script_dir.parent.parent
        for _pkg in ["ai", "bus", "langgraph", "capability_registry"]:
            _src = _packages_root / _pkg / "src"
            if _src.exists() and str(_src) not in sys.path:
                sys.path.insert(0, str(_src))
        from chat import AssistantChatService
        _chat_service = AssistantChatService()
    return _chat_service
```

**Problems:**
1. **No ports wired** — `AssistantChatService()` is created with all ports `None`
2. **sys.path manipulation** — modifies import path at runtime to enable flat imports
3. **Mixed concerns** — HTTP route handlers contain service composition logic
4. **Global mutable state** — `_chat_service` module-level variable
5. **Implicit dependencies** — the function silently imports from `ai`, `bus`, `langgraph`, `capability_registry`

### Multiple Competing Composition Roots

- **API composition**: `workflow_runner/api.py` creates `AssistantChatService`
- **MCP composition**: `workflow_runner/mcp_server.py` creates `CapabilityRegistry`
- **Runtime composition**: `workflow_runner/src/runtime.py` creates `PatternRuntime`
- **No central wiring**: Each module wires its own dependencies independently

### Conclusion

The system **does not have a clear, single composition root**. Composition is
distributed, implicit, and mixed with framework/transport concerns. This makes
it difficult to:
- Understand the full object graph
- Swap implementations (e.g., replace `LangGraphRuntime` with a test double)
- Enforce architectural boundaries at assembly time
- Verify that all ports are wired before deployment

## 2. Port Implementations

### Current State

**No production implementations exist for any of the 7 AI outbound ports.**

All ports are defined as `Protocol` classes in `packages/ai/src/ports/`, but
there are no concrete implementations outside of test fixtures.

| Port | Interface Location | Production Implementation | Test Fixture |
|------|-------------------|--------------------------|--------------|
| `CapabilityDiscoveryPort` | `packages/ai/src/ports/capability_discovery.py` | None | `InMemoryCapabilityDiscoveryPort` |
| `CapabilityExecutionPort` | `packages/ai/src/ports/capability_execution.py` | None | `InMemoryCapabilityExecutionPort` |
| `EnterpriseInformationPort` | `packages/ai/src/ports/enterprise_information.py` | None | `InMemoryEnterpriseInformationPort` |
| `OrganisationalContextPort` | `packages/ai/src/ports/organisational_context.py` | None | `InMemoryOrganisationalContextPort` |
| `PatternExecutionPort` | `packages/ai/src/ports/pattern_execution.py` | None | `InMemoryPatternExecutionPort` |
| `SessionFactoryPort` | `packages/ai/src/ports/session_factory.py` | None | `InMemorySessionFactoryPort` |
| `WorkManagementPort` | `packages/ai/src/ports/work_management.py` | None | `InMemoryWorkManagementPort` |

### Where Implementations Should Live

Based on the four-plane architecture and current package responsibilities:

| Port | Likely Provider Plane | Suggested Package | Rationale |
|------|----------------------|-------------------|-----------|
| `CapabilityDiscoveryPort` | People/Capability | `capability_registry` or new `people_capability` | CapabilityRegistry already exists; natural adapter |
| `CapabilityExecutionPort` | Operations | `workflow_runner` | `execute_capability()` and `PatternRuntime` already live here |
| `EnterpriseInformationPort` | Enterprise/EIMS | `capability_registry` (adapter) or new `eims` | ConceptStore is current EIMS; adapter already exists |
| `OrganisationalContextPort` | Organisation/Control | `organisation` | `OrganisationControlPlane.get_organisational_context()` already provides this |
| `PatternExecutionPort` | Operations | `workflow_runner` or `bus` | `PathwayRuntime` interface lives in `bus`; `LangGraphRuntime` in `langgraph` |
| `SessionFactoryPort` | Operations | `workflow_runner` | `create_session_from_decision()` lives in `workflow_runner` |
| `WorkManagementPort` | Organisation/Control | `organisation` | `OrganisationControlPlane` already has `assign_work()`, `get_work()`, `mark_work_ready()` |

### Dependency Direction Analysis

The fundamental tension: **Consumer defines interface, provider implements it.**

This means provider packages must import from `ai.src.ports.*`, creating a
dependency from provider → consumer.

**Current cross-plane dependencies in production code:**

| Source | Target | Nature |
|--------|--------|--------|
| `workflow_runner/api.py` | `ai` | Already imports `AssistantChatService` |
| `ai/src/ceo.py` | `organisation_control_plane` | Already imports `OrganisationControlPlane` |
| `workflow_runner/src/runtime.py` | `capability` | Already imports `Capability` |
| `workflow_runner/src/runtime.py` | `bus` | Already imports `EventBus` |
| `workflow_runner/src/mcp_server.py` | `capability_registry` | Already imports `CapabilityRegistry` |

**Circular dependency risk assessment:**

| Port Implementation Location | Would create circular dep? | Reason |
|------------------------------|---------------------------|--------|
| `workflow_runner` implements `PatternExecutionPort` | No | `workflow_runner` → `ai` already exists in `api.py` |
| `workflow_runner` implements `SessionFactoryPort` | No | Same as above |
| `workflow_runner` implements `CapabilityExecutionPort` | No | Same as above |
| `capability_registry` implements `CapabilityDiscoveryPort` | No | No existing `capability_registry` → `ai` dependency |
| `capability_registry` implements `EnterpriseInformationPort` | No | No existing `capability_registry` → `ai` dependency |
| `organisation` implements `OrganisationalContextPort` | **YES** | `ai/src/ceo.py` already imports `OrganisationControlPlane` from `organisation` |

**Critical finding:** `ai/src/ceo.py` imports `OrganisationControlPlane` from
`organisation`. If `organisation` were to implement `OrganisationalContextPort`,
it would need to import from `ai.src.ports.organisational_context`, creating a
circular dependency:

```
ai → organisation (ceo.py imports OrganisationControlPlane)
organisation → ai (to implement OrganisationalContextPort)
```

## 3. Adapter Ownership Rule

### Proposed Rule

```text
Consumer owns interface (in consumer's ports/ directory)
Provider owns implementation (in provider's package)
Composition root wires them together
```

### Violations and Tensions

#### Violation 1: `ai` → `organisation` (existing)

`ceo.py` directly imports `OrganisationControlPlane` from `organisation`. This
is a cross-plane dependency that bypasses the port mechanism.

**Options:**
1. Accept the dependency as "strategic role" exception (CEO is allowed to know about Organisation)
2. Move `OrganisationControlPlane` interface to a shared contracts package
3. Create a separate `OrganisationContextPort` that `organisation` implements without importing from `ai`

#### Violation 2: `workflow_runner` → `ai` (existing)

`api.py` imports `AssistantChatService` from `ai`. This is already a production
cross-plane dependency.

**Options:**
1. Accept as "application integration" exception
2. Move `AssistantPort` (the external interface) to a shared contracts package
3. Have `api.py` depend on `AssistantPort` only, not `AssistantChatService`

#### Violation 3: Port interface location vs. provider location

Ports are defined in `ai/src/ports/` but implemented by other planes. This means
providers must depend on `ai` to implement the interfaces.

**This is the Dependency Inversion Principle applied at the package level.**
It's a valid pattern, but it creates:
- Awkward dependency directions
- Potential circular dependencies (as seen with `organisation`)
- Provider packages must know about consumer's interface definitions

**Alternative:** Move port interfaces to a neutral `contracts` package that both
consumer and provider can import without creating hierarchical dependencies.

## 4. Additional Findings

### sys.path Manipulation

`workflow_runner/api.py` (lines 40-41, 622-625) manipulates `sys.path` to
enable flat imports across packages:

```python
for _pkg in ["ai", "bus", "langgraph", "capability_registry"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
```

This is a composition root anti-pattern. It:
- Hides the actual dependency structure
- Makes the code fragile to directory layout changes
- Prevents static analysis tools from understanding dependencies
- Creates runtime import errors if paths are misconfigured

### No DI Framework

The project uses manual constructor injection. There is:
- No service locator
- No DI container
- No factory pattern for complex object graphs
- No interface segregation at the package level

### Module-Level Instantiation

`mcp_server.py` creates `CapabilityRegistry` at module level (line 60), which
means it runs at import time. This makes testing difficult and creates hidden
dependencies.

### `PathwayRuntime` Location

`PathwayRuntime` interface lives in `packages/bus/src/pathway_runtime.py`. This
is a stable abstraction that both `langgraph` (implementation) and `workflow_runner`
(consumer) depend on. This is a good example of the "shared contracts" pattern.

## 5. Recommendations for Increment 16

### A. Establish a Single Composition Root

Create a dedicated composition module (e.g., `packages/workflow_runner/src/composition.py`
or a new `packages/composition/src/`) that:

1. Instantiates all concrete port implementations
2. Wires them into `AssistantChatService`, `CEOAgent`, etc.
3. Is the **only** place where concrete implementations are created
4. Is called by `api.py` and `mcp_server.py`, not the other way around

### B. Decide on Port Interface Ownership

Choose one of:

**Option 1: Consumer owns (current)**
- Keep ports in `ai/src/ports/`
- Providers import from `ai` to implement
- Risk: circular dependencies (already hit with `organisation`)

**Option 2: Neutral contracts package**
- Create `packages/contracts/src/` for shared interfaces
- Both consumer and provider import from `contracts`
- Risk: contracts package becomes a dumping ground

**Option 3: Provider owns interfaces**
- Ports live in provider packages
- Consumer imports from provider
- Risk: consumer depends on provider implementations, defeating the purpose

**Recommendation:** Option 2 (neutral contracts) for ports that providers must
implement. Keep `AssistantPort` in `ai` since it's the external interface
provided BY Assistant.

### C. Resolve `ai` ↔ `organisation` Circular Dependency

Since `ceo.py` already imports `OrganisationControlPlane`, either:
1. Move `OrganisationControlPlane` ABC to `contracts` package
2. Accept `ceo.py`'s direct import as a strategic exception and create a
   separate `OrganisationalContextPort` in `contracts` for `AssistantChatService`

### D. Port Implementation Order

Implement ports in this order to minimize risk:

1. `PatternExecutionPort` → `workflow_runner` (no circular risk, existing dependency)
2. `SessionFactoryPort` → `workflow_runner` (same)
3. `CapabilityExecutionPort` → `workflow_runner` (same)
4. `EnterpriseInformationPort` → `capability_registry` (no circular risk)
5. `CapabilityDiscoveryPort` → `capability_registry` (same)
6. `WorkManagementPort` → `organisation` (requires resolving circular dep first)
7. `OrganisationalContextPort` → `organisation` (requires resolving circular dep first)

## 6. Open Questions

1. Should there be a `contracts` package, or is the current "consumer owns"
   pattern acceptable with careful circular-dependency avoidance?
2. Should `ceo.py`'s direct `OrganisationControlPlane` import be refactored,
   or is CEO legitimately a special case that needs direct organisational access?
3. Should `AssistantChatService` remain in `workflow_runner/api.py`'s composition,
   or should the API layer depend on an `AssistantPort` interface instead?
4. Is `workflow_runner` the right place for the composition root, or should it
   be higher-level (e.g., in the API package or a new `application` package)?
