# Increment 16 — Application Composition, Port Implementations, and Cross-Plane Adapters: Implementation Plan

## Goal

Establish a single composition root, resolve port/interface ownership, implement the minimum production adapters to make Assistant composition real, and remove scattered production composition. Preserve all existing passing tests.

## Current State (from Increment 16 Investigation)

- Increment 15 committed and pushed (`fa98bcf`)
- AI tests: 45 passed; full suite: 255 passed; ruff clean
- `AssistantChatService` accepts ports via constructor but all ports are `None` in production
- `workflow_runner/api.py:_get_chat_service()` is the de facto composition root — it creates `AssistantChatService()` with no ports wired, manipulates `sys.path`, and uses a module-level singleton
- No production implementations exist for any of the 7 AI outbound ports
- `ai/src/ceo.py` imports `OrganisationControlPlane` from `organisation`, creating circular-dependency risk if `organisation` implements `OrganisationalContextPort`
- `workflow_runner/src/mcp_server.py` creates `CapabilityRegistry` at module level
- `workflow_runner/src/runtime.py` creates `CapabilityRegistry()` with defaults

## Phase 0 — Baseline Verification

Run before any changes:

```bash
pytest packages/ai/tests/ -q
pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py packages/capability_registry/tests/ packages/people_capability/tests/ packages/workflow_runner/tests/ -q
ruff check packages/ai/src/ packages/ai/tests/ packages/organisation/src/ packages/organisation/tests/ packages/capability_registry/src/ packages/capability_registry/tests/ packages/people_capability/src/ packages/people_capability/tests/ packages/workflow_runner/src/ packages/workflow_runner/tests/
```

Record: 45 AI tests pass, 255 full suite pass, ruff clean.

## Phase 1 — Establish Composition Root

**Decision: Create `packages/workflow_runner/src/composition.py`.**

Rationale:
- `workflow_runner/api.py` is already the de facto composition root for the Assistant
- It is the transport layer that needs to wire the application
- Creating a separate `packages/composition/` would add a new top-level package for minimal benefit
- The composition root belongs in the same package as the API that consumes it, or in a shared application package

**Do NOT create a DI framework.** Use explicit constructor injection.

**`composition.py` must export:**
- `create_application()` — wires all concrete services and returns a composed application object
- `create_assistant()` — wires only the Assistant and its ports
- `create_ceo()` — wires CEOAgent with its dependencies

**`composition.py` must NOT:**
- Contain business logic
- Be a service locator
- Use module-level singletons for services that take constructor arguments
- Import from `ai.src.chat` or `ai.src.ceo` at module level if it creates circular dependencies (use lazy imports inside factory functions if needed)

## Phase 2 — Solve Port Ownership

**Decision: Create `packages/contracts/src/` for cross-plane contracts that must be consumed by both application layer and provider planes.**

Rationale:
- Current "consumer owns interface" pattern creates provider → consumer dependencies
- `organisation` cannot implement `OrganisationalContextPort` without importing from `ai`, creating a circular dependency
- `capability_registry` cannot implement `CapabilityDiscoveryPort` without importing from `ai`, creating a new dependency
- A neutral `contracts` package breaks the cycle while keeping interfaces separate from implementations

**What goes in `contracts`:**
- `OrganisationalContextPort` — must be implemented by `organisation`, consumed by `ai`
- `WorkManagementPort` — must be implemented by `organisation`, consumed by `ai`
- `EnterpriseInformationPort` — must be implemented by `capability_registry`, consumed by `ai`
- `CapabilityDiscoveryPort` — must be implemented by `capability_registry`, consumed by `ai`
- `CapabilityExecutionPort` — must be implemented by `workflow_runner`, consumed by `ai`
- `PatternExecutionPort` — must be implemented by `workflow_runner`, consumed by `ai`
- `SessionFactoryPort` — must be implemented by `workflow_runner`, consumed by `ai`

**What stays in `ai`:**
- `AssistantPort` — this is the external interface provided BY Assistant, not consumed by providers
- `AssistantChatService`, `CEOAgent`, `AssistantReasoningService` — AI implementation details
- `intent`, `strategy`, `enterprise_context` — AI domain logic

**DTO placement:**
- DTOs that are only used by one port stay with that port in `contracts`
- `CapabilityCandidate` stays with `CapabilityDiscoveryPort`
- `PreviousSolution` stays with `EnterpriseInformationPort`
- `OrganisationalContext` stays with `OrganisationalContextPort`
- etc.

**`contracts` must NOT:**
- Import concrete implementations from any provider plane
- Import from `ai.src.chat`, `ai.src.ceo`, or any AI implementation
- Contain business logic
- Become a dumping ground for unrelated types

## Phase 3 — Resolve CEO / Organisation Dependency

**Decision: Refactor `ceo.py` to depend on `OrganisationalContextPort` from `contracts` instead of `OrganisationControlPlane` from `organisation`.**

Rationale:
- `ceo.py` currently imports `OrganisationControlPlane` directly
- This is a cross-plane dependency that bypasses the port mechanism
- It creates circular-dependency risk when `organisation` implements `OrganisationalContextPort`
- CEO is an AI-plane strategic role; it should interact with Organisation through ports, not concrete types

**Exception:** If `CEOAgent` genuinely requires `OrganisationControlPlane`-specific methods that are not in `OrganisationalContextPort` (e.g., `assign_work`, `delegate_authority`, `mark_work_ready`), then:
1. Document why CEO legitimately needs those methods
2. Keep the direct import but move `OrganisationControlPlane` ABC to `contracts` so both planes can import it without circular dependency

**Do NOT perform a broad CEO rewrite.** Only change the dependency direction to break the cycle.

## Phase 4 — Implement Minimum Provider Adapters

Implement adapters in this order (lowest risk first):

### 4.1 Operations Adapters (in `workflow_runner`)

**`PatternExecutionPort` adapter → `workflow_runner/src/adapters/pattern_execution_adapter.py`**
- Wraps existing `PathwayRuntime.invoke()` and `resume()`
- Translates `PatternExecutionRequest` → `PathwayCallRequest`
- Translates `PathwayResponse` → `PatternExecutionResult`
- Uses existing `LangGraphRuntime` or injected `PathwayRuntime`

**`SessionFactoryPort` adapter → `workflow_runner/src/adapters/session_factory_adapter.py`**
- Wraps existing `create_session_from_decision()`
- Translates `strategy`, `pattern_pipeline`, `context` → `Session`
- Returns `SessionReference`

**`CapabilityExecutionPort` adapter → `workflow_runner/src/adapters/capability_execution_adapter.py`**
- Wraps existing `execute_capability()`
- Translates `capability_id`, `context`, `actor_context` → `ExecutionResult`

### 4.2 Enterprise/Capability Adapters (in `capability_registry`)

**`EnterpriseInformationPort` adapter → `capability_registry/src/adapters/enterprise_information_adapter.py`**
- Wraps existing `ConceptStore` queries
- Translates `strategy_tag` → `ConceptStore.list_by_tag()` → `PreviousSolution`
- Uses existing `ConceptStoreCapabilityRepository` or injects `ConceptStore`

**`CapabilityDiscoveryPort` adapter → `capability_registry/src/adapters/capability_discovery_adapter.py`**
- Wraps existing `CapabilityRegistry.list_all()` and `CapabilityMatcher.match()`
- Translates `request_text`, `context` → `list[CapabilityCandidate]`

### 4.3 Organisation Adapters (in `organisation`)

**Only implement if Phase 3 leaves CEO needing them.**

**`OrganisationalContextPort` adapter → `organisation/src/adapters/organisational_context_adapter.py`**
- Wraps `OrganisationControlPlane.get_organisational_context()`
- Translates request → `OrganisationalContext`

**`WorkManagementPort` adapter → `organisation/src/adapters/work_management_adapter.py`**
- Wraps `OrganisationControlPlane.assign_work()`, `get_work()`, `mark_work_ready()`
- Translates `WorkCreateRequest` → `Assignment` / `Work`

**Each adapter must:**
- Be thin (DTO translation + delegation)
- Not introduce new business logic
- Live in the provider plane
- Import the port interface from `contracts` and the concrete implementation from its own plane

## Phase 5 — Assistant Composition

**Refactor `workflow_runner/api.py`:**

1. Remove `_get_chat_service()` function and `_chat_service` global
2. Import `create_assistant` from `composition.py`
3. In startup/shutdown or route handlers, call `create_application()` once and store the result
4. Pass the composed Assistant to route handlers

**`api.py` must NOT:**
- Instantiate `CapabilityRegistry`
- Instantiate `ConceptStore`
- Instantiate `LangGraphRuntime`
- Manipulate `sys.path` for application composition
- Call `AssistantChatService()` with no ports

**If lazy construction is required:** delegate to `composition.create_assistant()` rather than recreating composition logic inline.

## Phase 6 — Remove Scattered Composition

**`workflow_runner/src/mcp_server.py`:**
- Remove module-level `_authoring_registry = CapabilityRegistry(...)`
- Inject registry via function parameter or composition root

**`workflow_runner/src/runtime.py`:**
- Remove default `CapabilityRegistry()` construction
- Require registry injection (already supported via constructor parameter)

**`workflow_runner/api.py` line 755:**
- Remove `ConceptStore()` instantiation inside request handler
- Use injected EIMS adapter from composition root

## Phase 7 — Architectural Guardrails

Add tests to `packages/workflow_runner/tests/`:

1. **Composition root exists:** `composition.py` exports `create_application` and `create_assistant`
2. **No direct service construction in api.py:** AST test that `api.py` does not contain `CapabilityRegistry(`, `ConceptStore(`, `LangGraphRuntime(`, `sys.path.insert`
3. **No module-level registry in mcp_server.py:** AST test that `mcp_server.py` does not instantiate `CapabilityRegistry` at module level
4. **No circular dependency:** `contracts` does not import from `ai`, `organisation`, `workflow_runner`, or `capability_registry`; `ai` does not import `OrganisationControlPlane` directly
5. **Provider adapters are thin:** Each adapter file contains only DTO translation and delegation, no business logic
6. **AI does not import domain implementations:** Extend existing `test_ai_src_has_no_cross_plane_imports` to cover `ceo.py` after refactor

## Phase 8 — Behavioural Validation

All existing tests must continue to pass:
- `pytest packages/ai/tests/ -q` — 45 passed
- `pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py packages/capability_registry/tests/ packages/people_capability/tests/ packages/workflow_runner/tests/ -q` — 255 passed
- `ruff check` across all packages — clean

No speculative behaviour added.

## Strict Scope

**DO NOT implement:**
- Capability matching redesign
- Capability lifecycle redesign
- PatternRuntime authorisation enforcement
- CEO/COO/PM redesign
- Paperclip
- EIMS expansion
- ConceptStore relocation
- Universal routing
- Work creation redesign
- Organisational coordination redesign
- New domain models
- New business logic
- DI framework
- Service locator

**If a necessary architectural issue requires one of these, STOP and report it.**

## Implementation Order

| Step | Action | Risk | Test Impact |
|------|--------|------|-------------|
| 1 | Create `packages/contracts/src/` with all 7 port interfaces + DTOs moved from `ai/src/ports/` | Medium | Update imports in `ai/src/chat.py`, `ai/src/ceo.py`, test fixtures |
| 2 | Create `packages/workflow_runner/src/composition.py` with factory functions | Low | None |
| 3 | Refactor `ai/src/ceo.py` to use `OrganisationalContextPort` from `contracts` | Medium | Update `test_ceo.py` |
| 4 | Implement `PatternExecutionPort` adapter in `workflow_runner` | Low | Update `test_phase6.py` |
| 5 | Implement `SessionFactoryPort` adapter in `workflow_runner` | Low | Update `test_phase6.py` |
| 6 | Implement `CapabilityExecutionPort` adapter in `workflow_runner` | Low | None |
| 7 | Implement `EnterpriseInformationPort` adapter in `capability_registry` | Medium | Update `test_assistant.py`, `test_ceo.py` |
| 8 | Implement `CapabilityDiscoveryPort` adapter in `capability_registry` | Medium | Update `test_assistant.py` |
| 9 | Implement `OrganisationalContextPort` adapter in `organisation` | Medium | Update tests |
| 10 | Implement `WorkManagementPort` adapter in `organisation` | Medium | Update tests |
| 11 | Refactor `workflow_runner/api.py` to use composition root | Medium | Update `test_phase6.py` |
| 12 | Remove scattered composition in `mcp_server.py` and `runtime.py` | Low | Update tests |
| 13 | Add architectural guardrail tests | Low | None |
| 14 | Full validation run | — | Must pass |

## Key Decision Required Before Implementation

**Should `contracts` be a top-level `packages/contracts/` or a sub-package?**

**Recommended:** Top-level `packages/contracts/src/`.

Reasoning:
- Both `ai` (consumer) and provider planes (`organisation`, `capability_registry`, `workflow_runner`) must import from it
- A sub-package inside any provider would recreate the circular dependency
- A sub-package inside `ai` would violate "consumer owns interface" (provider would depend on AI sub-package)
- Top-level is the only neutral location
