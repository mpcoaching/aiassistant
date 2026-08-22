# Increment 14 — People/Capability Plane: Architectural Correction Implementation Plan

## Goal

Establish People/Capability as a genuine peer domain plane by:
1. Moving domain models (`Person`, `Agent`, `Capability`) to `packages/people_capability/src/`
2. Separating execution metadata from the `Capability` domain model
3. Introducing `CapabilityRepository` interface to decouple `CapabilityRegistry` from `ConceptStore`
4. Creating `CapabilityAssignment` and `CapabilityProficiency` models
5. Defining narrow query interfaces for capability matching and operations authorisation
6. Preserving all 55 existing tests

## Critical Architectural Corrections

### Correction 1: Execution metadata belongs to Operations

`CapabilityDeployment`, `ExecutionMode`, `Transport`, `AiSpec`, and `CompiledRef` are
operational execution concerns. They live in the Operations plane:
`packages/workflow_runner/src/capability_deployment.py`.

`PatternRuntime` consumes `CapabilityDeployment` directly. People/Capability defines the
shape; Operations owns the records and runtime dispatch.

### Correction 2: Invocation recording is operational telemetry

`record_invocation()` is removed from `CapabilityRepository`. It is not a domain repository
operation. It belongs to operational telemetry (e.g., `PatternRuntime` or a telemetry
interface in `workflow_runner`).

### Correction 3: CapabilityRegistry owns only domain catalog operations

`CapabilityRegistry` provides: `register`, `get`, `list`, `resolve`, `promote` (domain
maturation only). It depends on `CapabilityRepository` for persistence. It does not own
execution metadata or invocation telemetry.


## Current Implementation State

Significant progress has been made. The following is the current state:

### Completed
- `packages/people_capability/src/` created with: `person.py`, `agent.py`, `capability.py`, `capability_assignment.py`, `capability_proficiency.py`, `capability_repository.py`, `execution_authorisation.py`, `__init__.py`
- `packages/organisation/src/role.py` updated to import `Person`/`Agent` from `people_capability` instead of defining them
- `packages/capability_registry/src/capabilities.py` updated to import `Capability` from `people_capability`, removed execution fields from `Capability` model
- `packages/capability_registry/src/concept_store_adapter.py` created
- `packages/workflow_runner/src/capability_deployment.py` created with `ExecutionMode`, `Transport`, `AiSpec`, `CompiledRef`, `CapabilityDeployment`
- `packages/workflow_runner/src/runtime.py` updated to consume `CapabilityDeployment`
- `packages/workflow_runner/src/executor.py` moved from `capability_registry/src/executor.py`
- `packages/conftest.py` updated to include `people_capability` in sys.path
- 240+ tests passing

### Remaining Test Failures (Increment 14 regressions)

These are tests that need updating due to the architectural changes:

1. **`capability_registry/tests/test_capabilities.py`** (3 failures):
   - `test_record_invocation_updates_maturation` — `record_invocation()` removed from registry
   - `test_promote_sets_compiled` — `promote()` no longer sets `execution_mode`/`compiled_ref`
   - `test_skillrecord_maps_to_capability` — old execution mode mapping

2. **`capability_registry/tests/test_executor.py`** (5 failures):
   - Executor moved to `workflow_runner/src/executor.py`
   - Tests need updated imports and possibly adjusted to use `CompiledRef` from `capability_deployment`

3. **`workflow_runner/tests/test_phase3.py`** (2 failures):
   - `test_invoke_step_tier2_calls_run_directly` — `invoke_step` now requires `deployment` parameter
   - `test_invoke_step_tier3_returns_capability_reply` — same

4. **`workflow_runner/tests/test_e2e.py`** (1 failure):
   - `test_capability_invocation_end_to_end` — passes `ConceptStore` directly instead of adapter

5. **`workflow_runner/tests/test_phase5.py`** (2 failures):
   - `test_session_close_records_learnings` — calls removed `record_invocation()`
   - `test_learning_loop_promotes_capability_after_threshold` — same

### Pre-existing Failures (NOT Increment 14 regressions)

1. **`capability_registry/tests/test_knowledge_bus.py`** (2 failures):
   - `test_bus_declare_topology_registers_new_exchanges`
   - `test_capability_envelope_roundtrip`
   - Reason: `bus` module lacks `CapabilityRequest` attribute — unrelated to Increment 14

2. **`workflow_runner/tests/test_phase6.py::test_chat_service_returns_previous_solution`** (1 failure):
   - Status mismatch: expects `awaiting_confirmation`, gets `awaiting_capability_selection`
   - AssistantChatService bypass is explicitly deferred to Increment 15

### Remaining Implementation Steps

1. Fix `capability_registry/tests/test_capabilities.py` — update tests for new `promote()` and remove `record_invocation` tests
2. Fix `capability_registry/tests/test_executor.py` — update imports and adapt to moved executor
3. Fix `workflow_runner/tests/test_phase3.py` — pass `CapabilityDeployment` to `invoke_step()`
4. Fix `workflow_runner/tests/test_e2e.py` — wrap `ConceptStore` in adapter
5. Fix `workflow_runner/tests/test_phase5.py` — remove or update `record_invocation` calls
6. Add `packages/people_capability/tests/` — basic model tests and architectural boundary tests
7. Run full validation suite
8. Update documentation where permissions allow

## Constraints

- No production implementation of matching, lifecycle, or authorisation enforcement
- No Paperclip integration
- No EIMS expansion
- No AssistantChatService bypass fix (deferred to I15)
- No ConceptStore package relocation (deferred to I15)
- No CEO/COO/PM implementation changes
- Execution metadata and invocation telemetry belong to Operations, not People/Capability

## Task 1: Create people_capability package structure

**Files to create:**
- `packages/people_capability/src/__init__.py`
- `packages/people_capability/src/person.py` — `Person` model (moved from organisation)
- `packages/people_capability/src/agent.py` — `Agent` model (moved from organisation)
- `packages/people_capability/src/capability.py` — `Capability` model (moved from capability_registry, stripped of execution fields)
- `packages/people_capability/src/capability_assignment.py` — `CapabilityAssignment` model
- `packages/people_capability/src/capability_proficiency.py` — `CapabilityProficiency` model
- `packages/people_capability/src/exceptions.py` — domain exceptions

**Key decision:** `Person`, `Agent`, and `Capability` are the domain models. They import only
`pydantic` and standard library. No organisational, operational, or EIMS imports.

**Validation:** Run `pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py -q` — all 55 tests must pass.

## Task 2: Move Person and Agent from organisation

**Source:** `packages/organisation/src/role.py` — `Person` and `Agent` classes (lines 71-98)

**Target:** `packages/people_capability/src/person.py` and `packages/people_capability/src/agent.py`

**Changes required:**
1. `packages/organisation/src/role.py` — remove `Person` and `Agent` class definitions
2. `packages/organisation/src/role.py` — add `from person import Person` and `from agent import Agent`
3. `packages/organisation/src/organisation_control_plane.py` — update imports to use `Person` and `Agent` from `people_capability`
4. All organisation tests that import `Person` or `Agent` from `role` must import from `people_capability` instead

**Architectural guardrail test:** `test_no_person_agent_imports` already exists in
`test_role_model.py`. It must continue to pass. Add a new test that verifies `role.py`
does NOT define `Person` or `Agent` classes (only imports them).

## Task 3: Move Capability to people_capability (stripped)

**Source:** `packages/capability_registry/src/capabilities.py` — `Capability` class (lines 74-85)

**Strip the following fields:**
- `execution_mode`
- `transport`
- `ai_spec`
- `compiled_ref`

**Keep:**
- `capability_kind`
- `interface`
- `owns_durable_state`
- `standing_contract`

**Target:** `packages/people_capability/src/capability.py`

**Changes required:**
1. `packages/capability_registry/src/capabilities.py` — remove `Capability` class definition
2. `packages/capability_registry/src/capabilities.py` — add `from capability import Capability`
3. Update `CapabilityRegistry.register()` — ensure it still validates `capability.kind == ConceptKind.CAPABILITY`
4. Update all tests that construct `Capability(...)` directly
5. Update `mcp_server.py` and `api.py` if they construct `Capability` directly

**Validation:** All 55 existing tests + capability_registry tests must pass.

## Task 4: Create CapabilityAssignment and CapabilityProficiency

**Files to create:**
- `packages/people_capability/src/capability_assignment.py`
- `packages/people_capability/src/capability_proficiency.py`

**Models defined in investigation report (Section 9 and 10).**

**Tests to create:**
- `packages/people_capability/tests/test_capability_assignment.py`
- `packages/people_capability/tests/test_capability_proficiency.py`

## Task 5: Create CapabilityRepository interface and adapter

**Files to create:**
- `packages/people_capability/src/capability_repository.py` — `CapabilityRepository` protocol
- `packages/capability_registry/src/concept_store_adapter.py` — `ConceptStoreCapabilityRepository`

**Interface:**
```python
class CapabilityRepository(Protocol):
    def upsert(self, capability: Capability) -> None: ...
    def get(self, capability_id: str) -> Capability | None: ...
    def list_by_kind(self, kind: ConceptKind) -> list[Capability]: ...
```

**Note:** `record_invocation` is NOT part of `CapabilityRepository`. Invocation recording
is operational telemetry, not a repository concern.

**Adapter:** Wraps existing `ConceptStore` to implement `CapabilityRepository` (without
`record_invocation`).

**Changes required:**
1. `CapabilityRegistry.__init__` — change signature to `def __init__(self, repository: CapabilityRepository | None = None) -> None:`
2. `CapabilityRegistry` — replace `self._store` with `self._repository`
3. Remove `record_invocation()` from `CapabilityRegistry` — invocation recording is operational telemetry
4. Simplify `promote()` to update only domain maturation state (remove execution_mode/compiled_ref changes)
5. Add `ConceptStoreCapabilityRepository` to `capability_registry`
6. Update all `CapabilityRegistry(ConceptStore(...))` constructions to use the adapter

**Tests to update:**
- All `test_capabilities.py` constructions
- All other tests that construct `CapabilityRegistry`
- Tests that call `record_invocation` via `CapabilityRegistry` must be updated or removed

## Task 6: Create CapabilityDeployment for execution bindings (Operations plane)

**File to create:**
- `packages/workflow_runner/src/capability_deployment.py`

**Model:**
```python
class ExecutionMode(str, Enum):
    AI_MEDIATED = "ai_mediated"
    COMPILED = "compiled"

class Transport(str, Enum):
    TIER2_INPROCESS = "tier2_inprocess"
    TIER3_BUS = "tier3_bus"

class Parameter(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str = ""

class AiSpec(BaseModel):
    purpose: str = ""
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[Parameter] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    prompt_template_ref: str | None = None

class CompiledRef(BaseModel):
    module_path: str
    entrypoint: str = "run"
    tests_passed: bool = False

class CapabilityDeployment(BaseModel):
    capability_id: str
    environment: str
    execution_mode: ExecutionMode
    transport: Transport
    ai_spec: AiSpec | None = None
    compiled_ref: CompiledRef | None = None
```

**Purpose:** Separates execution metadata from domain model. Same capability can have
different deployments per environment.

**Key decision:** `CapabilityDeployment` and all execution-specific types live in the
Operations plane (`packages/workflow_runner/src/`), NOT in `capability_registry`.
`PatternRuntime` consumes `CapabilityDeployment` directly.

## Task 7: Move invocation telemetry to Operations

**Concern:** `record_invocation()` currently lives on `CapabilityRegistry` and `ConceptStore`.
It updates `maturation_history` counters after execution. This is operational telemetry.

**Changes required:**
1. Remove `record_invocation()` from `CapabilityRepository` interface
2. Remove `record_invocation()` from `CapabilityRegistry`
3. Add `record_invocation(capability_id, outcome)` to `PatternRuntime` or a new
   `OperationalTelemetry` interface in `packages/workflow_runner/src/`
4. Update all callers:
   - `test_executor.py` calls `reg.record_invocation(cap.id, "success")` after execution
   - `test_capabilities.py` calls `reg.record_invocation(...)`
   - `test_phase5.py` calls via registry
   - `test_phase6.py` may call via registry
   These must be updated to use the operational telemetry interface

**Note:** `ConceptStore.record_invocation()` can remain as-is for now (it is the EIMS
implementation). The domain registry simply stops exposing it.

## Task 8: Define ExecutionAuthorisationPort interface

**File to create:**
- `packages/people_capability/src/execution_authorisation.py`

**Interface:**
```python
class ExecutionAuthorisationPort(Protocol):
    def is_authorised(
        self,
        actor_id: str,
        actor_type: str,
        capability_id: str,
    ) -> AuthorisationResult: ...
```

**Stub implementation:**
```python
class InMemoryExecutionAuthorisationPort:
    def __init__(self) -> None:
        self._assignments: dict[str, CapabilityAssignment] = {}
    
    def register_assignment(self, assignment: CapabilityAssignment) -> None: ...
    def is_authorised(self, actor_id, actor_type, capability_id) -> AuthorisationResult: ...
```

**Note:** Enforcement in `PatternRuntime` is deferred to a later increment. This increment
only defines the interface and provides a stub.

## Task 9: Update all imports and tests

**Imports to update:**
1. `packages/organisation/src/role.py` — remove `Person`, `Agent` definitions; add imports
2. `packages/organisation/src/organisation_control_plane.py` — update `Person`/`Agent` imports
3. `packages/capability_registry/src/capabilities.py` — add `Capability` import from people_capability
4. `packages/capability_registry/src/concept_store_adapter.py` — new file
5. `packages/ai/src/chat.py` — update `Capability` import path if needed
6. `packages/workflow_runner/src/runtime.py` — update `Capability` import path if needed
7. `packages/workflow_runner/src/capability_deployment.py` — new file
8. All test files that import from old locations

**Tests to update:**
- `packages/organisation/tests/test_role_model.py`
- `packages/organisation/tests/test_organisation_control_plane.py`
- `packages/organisation/tests/test_workflow_proof.py`
- `packages/capability_registry/tests/test_capabilities.py`
- `packages/capability_registry/tests/test_executor.py`
- `packages/capability_registry/tests/test_capability_matcher.py`
- `packages/capability_registry/tests/test_capability_request.py`
- `packages/capability_registry/tests/test_knowledge_bus.py`
- `packages/capability_registry/tests/test_concepts.py`
- `packages/ai/tests/test_ceo.py`
- `packages/ai/tests/test_assistant.py`
- `packages/workflow_runner/tests/test_phase3.py`
- `packages/workflow_runner/tests/test_phase5.py`
- `packages/workflow_runner/tests/test_phase6.py`
- `packages/workflow_runner/tests/test_e2e.py`

## Task 10: Add architectural guardrail tests

**New tests to create:**

1. `packages/people_capability/tests/test_architectural_boundaries.py`:
   - `test_person_capability_package_has_no_operational_imports`
   - `test_person_capability_package_has_no_organisation_imports`
   - `test_person_capability_package_has_no_eims_imports`
   - `test_capability_model_has_no_execution_fields`

2. `packages/organisation/tests/test_architectural_boundaries.py`:
   - `test_role_py_does_not_define_person_agent` (enhance existing)
   - `test_organisation_has_no_capability_execution_imports`

3. `packages/capability_registry/tests/test_architectural_boundaries.py`:
   - `test_capability_registry_does_not_import_concept_store`
   - `test_capability_registry_depends_on_repository_interface`
   - `test_capability_registry_has_no_record_invocation`

4. `packages/workflow_runner/tests/test_architectural_boundaries.py`:
   - `test_workflow_runner_owns_capability_deployment`
   - `test_capability_deployment_has_execution_fields`

## Task 11: Update architecture documentation

**Files to update:**
- `docs/architecture/INCREMENT-14-INVESTIGATION-REPORT.md`
- `docs/architecture/adr/ADR042-capability-execution-binding-separation.md`
- `docs/architecture/adr/ADR043-capability-repository-interface.md`
- `.kilo/context/architecture.md`

**Note:** `.kilo/context/architecture.md` update was blocked by file permissions in I13.
If still blocked, report the exact error and provide the diff as a patch file.

## Validation

After all tasks complete:
```
pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py packages/capability_registry/tests/ packages/people_capability/tests/ packages/workflow_runner/tests/ -q
Result: All pass
```

```
ruff check packages/people_capability/src/ packages/people_capability/tests/ packages/organisation/src/ packages/organisation/tests/ packages/capability_registry/src/ packages/capability_registry/tests/ packages/workflow_runner/src/ packages/workflow_runner/tests/
Result: All pass
```

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Import path breakage across packages | High | Medium | Systematic grep for all import statements before changing |
| Test fixture breakage | High | Medium | Run full test suite after each package change |
| CapabilityRegistry API breakage | Medium | Medium | Maintain identical public API; only internal wiring changes |
| Circular import between people_capability and organisation | Low | High | Use `str` forward references in type hints where needed |
| ConceptStore adapter mismatch | Low | Medium | Adapter is thin wrapper; test each method |
| Operations telemetry split | Medium | Medium | Move `record_invocation` callers incrementally |

## Deferred Items

- ConceptStore package relocation to `enterprise/eims` (Increment 15)
- AssistantChatService bypass fix (Increment 15)
- PatternRuntime authorisation enforcement (Increment 15+)
- Capability matching implementation (later increment)
- Capability lifecycle beyond assignment/proficiency (later increment)
- Paperclip integration (future)
- EIMS expansion (future)
