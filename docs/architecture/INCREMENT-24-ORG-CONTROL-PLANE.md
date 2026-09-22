# Increment 24 — Org Control Plane Solution Selection Boundary

## Summary

Established the first explicit boundary between BAU workflow execution and innovation/capability-development paths in the Org Control Plane.

## Architecture Discovered

### Current execution decision points

1. **AssistantChatService.chat()** (`packages/ai/src/chat.py:826-966`) — top-level routing between previous-solution lookup, capability discovery, AI, pattern execution, and work delegation
2. **CapabilityActionPolicy.decide()** (`packages/ai/src/capability_action.py:50-58`) — maps capability candidates to Execute/Select/Gap actions
3. **Worker.execute()** (`packages/workflow_runner/src/worker.py:60-88`) — routes between capability_development, capability execution, and generic work
4. **Operations._select_backend()** (`packages/workflow_runner/src/operations.py:250-255`) — selects WorkerBackend vs PaperclipBackend

### Workflow execution

- Entry point: `execute_workflow()` in `packages/workflow_runner/executor.py:31-139`
- Triggered by API: `POST /workflows/{name}/run` (`packages/workflow_runner/api.py:309-340`)
- `WorkflowDefinition` is a YAML-defined execution pattern (steps, not triggers)
- `WorkflowState` tracks execution instance progress
- `Work` is the organisational accountability unit — separate from `WorkflowState`

### Capability learning loop (preserved)

```
capability gap
  ↓
Work(capability_development)
  ↓
team/worker execution
  ↓
DRAFT Capability
  ↓
assessment
  ↓
evidence
  ↓
CapabilityProficiency
  ↓
ACTIVE Capability
```

## What Was Implemented

### 1. Execution path result model

**New file:** `packages/organisation/src/execution_path.py`

Small Pydantic model with four possible paths:
- `EXISTING_WORKFLOW`
- `CAPABILITY_PATH`
- `NEW_CAPABILITY_REQUIRED`
- `HUMAN_TEAM_INVESTIGATION`

### 2. Org Control Plane gains `select_execution_path`

**Modified:** `packages/organisation/src/organisation_control_plane.py`

Added abstract method to `OrganisationControlPlane` and implementation in `InMemoryOrganisationControlPlane`:

```python
def select_execution_path(
    self,
    intent: str,
    context: dict[str, Any],
    workflow_lookup: Callable[[str], list[Any]] | None = None,
) -> ExecutionPathResult:
```

Decision hierarchy:
1. If `workflow_lookup` returns matching workflows → `EXISTING_WORKFLOW`
2. If a required capability exists in the capability registry → `CAPABILITY_PATH`
3. Otherwise → `NEW_CAPABILITY_REQUIRED`

Workflow lookup is passed as a callback to avoid importing `workflow_runner` into the `organisation` package.

### 3. Paperclip implementation

**Modified:** `packages/organisation_paperclip/src/organisation_paperclip.py`

Added `select_execution_path` implementation. Paperclip does not maintain a workflow registry, so it falls back to capability checking only.

### 4. Solution selection port and adapter

**New file:** `packages/contracts/solution_selection.py`

```python
class SolutionSelectionPort(Protocol):
    def select_execution_path(self, intent: str, context: dict[str, Any]) -> SolutionSelectionResult | None: ...
```

**New file:** `packages/organisation/src/adapters/solution_selection_adapter.py`

Wraps `OrganisationControlPlane` as a `SolutionSelectionPort`.

### 5. Workflow execution port and adapter

**New file:** `packages/contracts/workflow_execution.py`

```python
class WorkflowExecutionPort(Protocol):
    def execute_workflow(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResult: ...
```

**New file:** `packages/workflow_runner/src/adapters/workflow_execution_adapter.py`

Executes workflows via the workflow_runner `executor`.

### 6. Assistant integration

**Modified:** `packages/ai/src/chat.py`

- Added `solution_selection` and `workflow_execution` constructor parameters
- Before capability discovery, calls `select_execution_path`
- If `EXISTING_WORKFLOW` is returned, executes the workflow via `WorkflowExecutionPort`
- Falls through to existing capability/workflow logic otherwise

### 7. Composition wiring

**Modified:** `packages/workflow_runner/src/composition.py`

- Created `_workflow_lookup` function that scans YAML workflow files
- Wired `SolutionSelectionAdapter` with workflow lookup
- Wired `WorkflowExecutionAdapter`
- Passed both to `create_assistant`

## Tests

### Layer 1 — Unit tests on Org Control Plane

**New file:** `packages/organisation/tests/test_execution_path.py`

- `test_existing_workflow_selected_when_matching`
- `test_no_workflow_returns_non_workflow_path`
- `test_capability_path_selected_when_no_workflow_but_capability_exists`
- `test_new_capability_required_when_neither_exists`
- `test_new_capability_required_when_capability_not_in_context`
- `test_workflow_selected_even_when_capability_exists`
- `test_workflow_selection_does_not_invoke_capability_development`
- `test_paperclip_control_plane_has_select_execution_path`
- `test_paperclip_select_execution_path_returns_new_capability_when_none_found`
- `test_execution_path_result_is_pydantic_model`
- `test_execution_path_result_serialises`
- `test_select_execution_path_without_workflow_lookup`

### Layer 2 — Integration through application stack

**Modified:** `packages/workflow_runner/tests/test_platform_integration.py`

Added `TestSolutionSelectionBoundary`:
- `test_workflow_selected_and_executed_for_known_intent` — Scenario A: BAU workflow execution, capability development NOT invoked
- `test_capability_path_selected_when_no_workflow` — Scenario B: capability execution path
- `test_innovation_path_creates_capability_development_work` — Scenario C: capability-gap Work created

### Layer 3 — Paperclip boundary

**Modified:** `packages/workflow_runner/tests/test_paperclip_integration.py`

Added `TestPaperclipExecutionBoundary`:
- `test_solution_selection_boundary_is_independent_of_execution_backend` — InMemory and Paperclip OCP return same path
- `test_paperclip_ocp_implements_solution_selection_port` — Paperclip OCP has the method

## Key Architectural Principles Established

1. **Org Control Plane owns solution selection** — `select_execution_path` is the explicit boundary
2. **BAU = understood, repeatable work executed through workflows** — known workflows get cheap, fast, predictable execution
3. **Innovation = uncertain/new work handled through organisational capability/team reasoning** — capability gap creates Work for development
4. **Capability != Workflow** — a capability is a reusable ability; a workflow is an understood execution pattern
5. **Workflow execution can occur without active team participation** — BAU workflows run autonomously
6. **Paperclip is below the Org Control Plane** — Paperclip executes work; it does not decide what kind of work
7. **LangGraph is below the Org Control Plane** — LangGraph implements execution mechanisms, not organisational semantics
8. **WorkflowDefinition remains an execution pattern, not a trigger/schedule definition** — triggers/schedules live elsewhere
9. **Learned capability → reusable workflow is a future path** — not automatically conflated

## What Remains Architectural Direction

- Full workflow compiler
- Automatic workflow synthesis
- Sub-flow registry
- Trigger/schedule domain model
- Autonomous teams
- Autonomous organisational restructuring
- Knowledge graph / RAG
- Generic event sourcing
- Sophisticated capability composition
- Capability maturity framework
- Workflow-to-capability automatic promotion

## Files Added

- `packages/organisation/src/execution_path.py`
- `packages/organisation/src/adapters/solution_selection_adapter.py`
- `packages/contracts/solution_selection.py`
- `packages/contracts/workflow_execution.py`
- `packages/workflow_runner/src/adapters/workflow_execution_adapter.py`
- `packages/organisation/tests/test_execution_path.py`

## Files Modified

- `packages/organisation/src/organisation_control_plane.py`
- `packages/organisation_paperclip/src/organisation_paperclip.py`
- `packages/workflow_runner/src/composition.py`
- `packages/ai/src/chat.py`
- `packages/contracts/__init__.py`
- `packages/workflow_runner/tests/test_platform_integration.py`
- `packages/workflow_runner/tests/test_paperclip_integration.py`

## Test Results

- **Layer 1:** 12/12 passed
- **Layer 2:** 3/3 passed
- **Layer 3:** 2/2 passed
- **All organisation tests:** 91 passed, 1 failed (pre-existing `test_api_does_not_import_paperclip` from WIP state)
- **All workflow_runner tests:** 419 passed, 4 skipped
- **ruff lint:** All checks passed

## Environment Limitations

- Paperclip integration tests mock the Paperclip API; a live Paperclip instance is not required
- The `test_api_does_not_import_paperclip` failure is from a previous increment's uncommitted WIP that imports `ai.src.paperclip_chat` in the API layer — not caused by this increment
