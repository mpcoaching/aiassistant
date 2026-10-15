# Increment 35 — Workflow Lifecycle & Adoption Authority

## Report

---

### A. WorkflowDefinition as boundary object

`WorkflowDefinition` is defined in `packages/workflow_runner/models.py` — it is an **infrastructure artifact of the execution engine**, not an organisational entity.

**Evidence**:
- `organisation/src/organisation_control_plane.py` does not import `WorkflowDefinition`. OCP's `select_execution_path` receives workflows via an opaque `workflow_lookup: Callable[[str], list[Any]]` callback. Whatever the callback returns is stored in `ExecutionPathResult.workflow` — which is typed `Any | None` (`packages/organisation/src/execution_path.py:29`) — and passed through to the execution port.
- The `OrganisationControlPlane` class is a Protocol in `packages/contracts/solution_selection.py` and an in-memory implementation in `packages/organisation/src/organisation_control_plane.py`. Neither imports or references `WorkflowDefinition` or anything from `workflow_runner`.
- The organisation plane's `execution_path.py` module docstring (`packages/organisation/src/execution_path.py:5`) explicitly states: *"Does not import from workflow_runner to preserve the organisational boundary."*
- `WorkflowDefinition` lives in `packages/workflow_runner/models.py`, not in the organisation package.

**Key finding**: OCP treats the execution pattern as an **opaque token**. It does not parse, validate, or inspect workflow internals. The pattern's structure (steps, inputs, outputs) is entirely an execution-engine concern.

---

### B. No separate Workflow entity

There is **no** `Workflow` identity class anywhere in the architecture. The two workflow-related concepts are:

| Concept | Where | Purpose |
|---|---|---|
| `WorkflowDefinition` | `packages/workflow_runner/models.py` | The explicit, declarative pattern (static) |
| `WorkflowState` | `packages/workflow_runner/models.py` | Runtime execution state of a pattern (mutable) |

**Evidence**:
- An AST scan of all `.py` files under `packages/workflow_runner/`, `packages/organisation/`, and `packages/contracts/` finds **zero** class definitions named exactly `Workflow`.
- `models.py` contains `WorkflowDefinition`, `WorkflowState`, but no `Workflow` intermediary.
- No `Workflow` class appears in `organisation/src/` or `contracts/`.

**Key finding**: No separate organisational `Workflow` identity is needed. The organisation only needs to know "this pattern is known" — which it discovers via `workflow_lookup` → `EXISTING_WORKFLOW`. The organisation never holds a `Workflow` object; it holds the execution *path decision*.

---

### D. Filesystem presence = creation mechanism (no adoption gate)

Workflow creation/write happens through:

1. **API endpoint** `packages/workflow_runner/api.py`
2. **Filesystem** (`agentic/docs/workflows/*.yaml`)
3. **Loader** (`resolve_workflow_path` / `load_workflow`)

There is **no adoption decision gate** between these steps. Writing the YAML file IS the adoption signal.

**Evidence**:
- `create_workflow` (`api.py:286`): Validates the name, constructs a `WorkflowDefinition`, and writes it to `agentic/docs/workflows/{name}.yaml` via `yaml.safe_dump`. No `adopt` check, no `approval` check.
- `list_workflows` (`api.py:267`): Globs `*.yaml` files from the workflow directories directly — no adoption status filter. Every YAML file on disk is exposed as a valid workflow.
- There is **no creation port** in `packages/contracts/` — no `WorkflowCreationPort` or `WorkflowAdoptionPort`.
- `WorkflowExecutionAdapter` (`adapters/workflow_execution_adapter.py:27`) loads YAML from disk and executes — it does not create or adopt.

**Key finding**: The YAML file's existence on the filesystem is the sole "adoption" signal. No human/system mediation occurs between "YAML written" and "OCP discovers it". This is acceptable for the current architecture but means there is no mechanism to distinguish "proposed" from "approved" workflows.

---

### I. Applicability / discoverability conflation

`build_workflow_lookup` (`packages/workflow_runner/src/composition.py:80`) collapses four concerns into one: **discovery**, **relevance**, **authority**, and **adoption**.

**Evidence**:
- The lookup function (`_workflow_lookup`) matches by simple keyword overlap between the intent string and the workflow's `name`/`description`. The matching logic:
  ```python
  intent_lower in name_lower
  or name_lower in intent_lower
  or (desc_lower and any(word in desc_lower for word in intent_lower.split())
  ```
- It does **not** perform semantic relevance assessment (no embedding/vector comparison).
- It does **not** check capability association (no `capability_id` on `WorkflowDefinition`).
- It does **not** check adoption status (no `adopted`, `status`, or "approved" filter).
- OCP's `select_execution_path` calls `workflow_lookup(intent)` and treats any non-empty result as `EXISTING_WORKFLOW` immediately — there is no "is this workflow adopted?" check. OCP has no `adopt`, `deprecat`, or `retire` methods.

**Key finding**: Discoverability, relevance, and adoption are all collapsed into "file exists on disk and its name/description textually overlaps with the intent." There is no quality bar, no capability binding, and no approval gate between "YAML exists" and "OCP recognises it as EXISTING_WORKFLOW".

---

### M. BAU directionality — Work/request drives workflow selection

The architectural flow is **directional**: the user's *intent* finds the *workflow*, not the reverse.

**Evidence**:
- `select_execution_path(intent: str, ...)` is called with the user's request text. It calls `workflow_lookup(intent)` — the workflow is discovered *in response to* the intent, not the other way around.
- A functional test confirms `workflow_lookup` is called with exactly `["analyse customer churn"]` — the raw intent string — not something derived from a workflow's internal structure.
- `select_execution_path` does **not** create a `Work` record. `list_work()` returns the same count (0) before and after calling `select_execution_path` with a matching workflow. Workflow selection and Work creation are independent.
- Neither `Work` (`packages/organisation/src/role.py`) nor `WorkflowDefinition` (`packages/workflow_runner/models.py`) has a `trigger`, `triggers`, `schedule`, or `cron` field. Workflow triggering (scheduling, event-driven execution) is not modelled in the domain — it would be an infrastructure concern.

**Key finding**: The lifecycle is: `request/intent → workflow lookup → EXISTING_WORKFLOW decision → execution`. The workflow does not retroactively create Work; Work does not retroactively create workflows. The directionality is request-driven, preventing circular causality where a workflow's existence could bootstrap its own adoption.

---

### N. Execution authorisation — workflow execution bypasses capability authorisation

The `WorkflowExecutionPort` does not carry actor identity, and the `WorkflowExecutionAdapter` does not check authorship.

**Evidence**:
- `WorkflowExecutionRequest` (`packages/contracts/workflow_execution.py:6`) contains only `workflow_name`, `initial_context`, and `role_override`. It has **no** `actor_id`, `actor_context`, or `actor_type` field.
- `WorkflowExecutionPort.execute_workflow` (`packages/contracts/workflow_execution.py:26`) has signature `(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResult` — no actor context parameter.
- `WorkflowExecutionAdapter.execute_workflow` (`adapters/workflow_execution_adapter.py:27`) does **not** reference `authorisation_port`, `is_authorised`, `ExecutionAuthorisationPort`, `actor_context`, or `actor_id`. It calls `resolve_workflow_path` → `execute_workflow_from_file` directly.
- By contrast, `CapabilityExecutionPort` (`packages/contracts/capability_execution.py`) *does* carry `actor_context` — capability-path execution is authorisation-checked per step.
- `WorkflowExecutionAdapter` has no dependency on `CapabilityExecutionPort` or anything from the capability execution path.

**Key finding**: A workflow is adopted (by YAML presence) but its execution **does not check** whether the executing actor is authorised for each capability in the workflow's steps. The `CapabilityExecutionPort` enforces authorisation; the `WorkflowExecutionPort` does not. This is acceptable **only if** workflows are pre-authorised by the organisation (the YAML file itself being the organisational decision). It would **not** be acceptable if individual per-step capability-level authorisation is required.

---

### O. Backend independence — runtimes and backends do not decide adoption

Workflow adoption and discovery is an **organisation-plane concern**. Backend runtimes and executors are infrastructure — they do not make adoption decisions.

**Evidence**:
- **LangGraphRuntime** (`packages/langgraph/src/langgraph_runtime.py:40`): Extends `PathwayRuntime`, implements `invoke`/`resume`. Has **no** `adopt`, `register_workflow`, `compile_workflow`, `create_workflow`, `promote_workflow`, or `synthesize` methods.
- **PatternRuntime** (`packages/workflow_runner/src/runtime.py:28`): Executes capability invocations via `invoke_step`. Has **no** workflow adoption, creation, or lifecycle methods — and notably does **not** have `select_execution_path`.
- **PaperclipOrganisationControlPlane** (`packages/organisation_paperclip/src/organisation_paperclip.py:534`): Implements `select_execution_path`, but its implementation **ignores** the `workflow_lookup` callback entirely. Its docstring reads: *"Paperclip does not maintain a workflow registry, so workflow lookup is not available here. Falls back to capability check."* The method body only checks `required_capability_ids` against `self._work_cache` — it never calls `workflow_lookup`, never returns `EXISTING_WORKFLOW`.
- **Worker** (`packages/workflow_runner/src/worker.py`): Executes Work via capability execution or generic work. Has **no** `select_execution_path`, `adopt`, `compile_workflow`, `create_workflow`, `register_workflow`, or `promote_workflow` methods.
- **Operations** (`packages/workflow_runner/src/operations.py`): Coordinates backends for READY Work based on `assignee_agent_id`. Source contains **no** `select_execution_path`, `WorkflowDefinition`, or `workflow_lookup` references. Backend selection is based on Work fields, not on workflow identity.

**Key finding**: Workflow discovery and adoption happen **exclusively** in the organisation control plane (OCP). Backups (Paperclip), executors (Worker, PatternRuntime), the orchestration layer (Operations), and runtimes (LangGraphRuntime) are all infrastructure — they execute patterns but never decide whether to adopt them. This cleanly separates the *organisation decision* ("what patterns are BAU") from the *execution* ("run the pattern").

---

### P. Architectural tests

Added **21 tests** in `packages/organisation/tests/test_increment35_lifecycle_adoption.py` covering findings not already covered by Increment 33 (execution boundary) or Increment 34 (evidence-to-adoption boundary).

| # | Test | Section |
|---|---|---|
| 1 | `test_ocp_does_not_import_workflow_definition` | A |
| 2 | `test_execution_path_result_workflow_is_opaque_any` | A |
| 3 | `test_workflow_definition_lives_in_workflow_runner_not_organisation` | A |
| 4 | `test_no_workflow_entity_exists` | B |
| 5 | `test_workflow_definition_is_the_sole_workflow_concept` | B |
| 6 | `test_api_create_workflow_writes_yaml_without_adoption_check` | D |
| 7 | `test_api_list_workflows_globs_filesystem_no_adoption_filter` | D |
| 8 | `test_build_workflow_lookup_matches_purely_by_keyword_not_semantics` | I |
| 9 | `test_ocp_treats_lookup_result_as_immediate_adoption` | I |
| 10 | `test_workflow_lookup_is_called_with_intent_not_workflow_driven` | M |
| 11 | `test_work_is_not_created_by_workflow_selection` | M |
| 12 | `test_explicit_workflow_trigger_is_infrastructure_not_organisation` | M |
| 13 | `test_workflow_execution_port_has_no_actor_context` | N |
| 14 | `test_workflow_execution_adapter_source_has_no_authorisation_check` | N |
| 15 | `test_workflow_execution_adapter_does_not_use_capability_execution_port` | N |
| 16 | `test_workflow_execution_bypasses_capability_authorisation_boundary` | N |
| 17 | `test_langgraph_runtime_has_no_workflow_adoption_methods` | O |
| 18 | `test_pattern_runtime_has_no_workflow_adoption_methods` | O |
| 19 | `test_paperclip_select_execution_path_ignores_workflow_lookup` | O |
| 20 | `test_worker_does_not_select_or_adopt_workflows` | O |
| 21 | `test_operations_does_not_decide_workflow_adoption` | O |

---

### Q. Code changes

**No production code changes.** The investigation confirms the architecture correctly maintains all five boundaries. The only file added is the test file above.

---

### R. Tests / results

```
packages/organisation/tests/test_increment35_lifecycle_adoption.py
  21 passed in 0.45s

Full suite (organisation tests only):
  327 passed (was 306 + 21 new)
  0 failed
  0 regressions

Ruff: All checks passed! on the new test file.
```

---

### S. Pre-existing failures

No pre-existing failures affected by this increment. (The organisation test suite is fully green: 327 passed, 0 failed.) The broader repo has 60 pre-existing integration test failures in `packages/workflow_runner/tests/test_capability_execute.py` and `test_platform_integration.py` (documented in Increment 34, sections R–S), which require external services and are **unrelated** to the workflow lifecycle/adoption boundary.

---

### T. Architectural gaps (confirmed / refined)

| Gap | Status | Detail |
|---|---|---|
| No `WorkflowAdoptionPort` in `contracts/` | **Confirmed** (same as Inc 34) | No organisational port for deciding whether an observed pattern becomes an adopted workflow. |
| No provenance on `WorkflowDefinition` | **Confirmed** (same as Inc 34) | No `source_work_ids`, `author`, `rationale`, or `approved_by`. |
| Filesystem presence = adoption | **Confirmed** (same as Inc 34) | `build_workflow_lookup` returns every YAML file; no "proposed/ adopted" status. |
| No capability↔workflow association | **Confirmed** (same as Inc 34) | `WorkflowDefinition` does not reference capabilities; OCP matches by intent string keywords only. |
| No versioning/supersession | **Confirmed** (same as Inc 34) | `WorkflowDefinition.version` is a schema version (`"1"`). |
| No failure feedback to revision | **Confirmed** (same as Inc 34) | No mechanism to feed execution failures back into revising the YAML. |
| **Workflow execution bypasses capability authorisation** | **Newly confirmed** (section N below) | `WorkflowExecutionPort` carries no actor context; execution does not check per-step capability authorisation. Acceptable only when the YAML file is pre-authorised by the organisation. |
| **No trigger/schedule model** | **Newly confirmed** (section M) | Neither `Work` nor `WorkflowDefinition` has trigger fields. Event-driven or scheduled workflow execution is not modelled in the domain. |

**All gaps are intentional** for the current architecture. They represent the boundaries between organisational decision-making and operational execution. They should remain unprogrammed until the organisation is ready to automate the adoption decision (a future increment).

---

### U. Lifecycle authority map

This increment produces a clear map of where lifecycle decisions live:

| Decision | Where it happens | Evidence |
|---|---|---|
| "Should this pattern be a workflow?" (understanding) | Human (external) | No entity or port; crystallised when YAML is written |
| "Should this workflow be adopted?" (adoption) | Human writes YAML to filesystem | No adoption check in `create_workflow`; filesystem presence = adopted |
| "Is this workflow discoverable?" (discovery) | `OCP.select_execution_path` + `build_workflow_lookup` | OCP calls `workflow_lookup(intent)`; any non-empty result → `EXISTING_WORKFLOW` |
| "How should this intent be executed?" (selection) | `OCP.select_execution_path` | Decision hierarchy: workflow → capability → human investigation → new capability |
| "Should this actor run this step?" (capability auth) | `CapabilityExecutionPort` (via `PatternRuntime._check_authorisation`) | `actor_context` flows through; `is_authorised()` checked per invocation |
| "Should this actor run this workflow?" (workflow auth) | **Not checked** | `WorkflowExecutionRequest` has no actor fields; `WorkflowExecutionAdapter` calls no authorisation port |
| "Which backend should execute this Work?" (assignment) | `Operations` (based on `assignee_agent_id`) | No workflow or capability involvement in backend selection |
| "When should this workflow run?" (triggering) | Not modelled | No trigger/schedule/cron fields on `Work` or `WorkflowDefinition` |

---

### V. Summary

Increment 35 confirms that the workflow lifecycle in this architecture is:

1. **Authoritative** — `OrganisationControlPlane` (the organisation plane) is the sole authority for discovering and selecting existing workflows. Paperclip's OCP variant does not participate in workflow discovery. Backend runtimes (LangGraphRuntime, PatternRuntime) and the Worker are pure executors with no adoption authority.

2. **Unidirectional** — The flow is `intent → workflow lookup → execution path decision → execution`. Work is not created by workflow selection. Workflows are not created by Work execution. The directionality is always request-driven.

3. **Externally adopted** — There is no programmatic adoption decision. The YAML file's existence on the filesystem is the sole adoption signal. This is a deliberate architectural seam.

4. **Unauthorised** — Workflow execution bypasses the capability-level authorisation that capability-path execution enforces, because `WorkflowExecutionPort` carries no actor context. This is acceptable only if the organisation pre-authorises workflows via the YAML file itself.

**No code changes were made.** The architecture already correctly maintains these boundaries. The 21 new tests document and enforce them, preventing future increments from accidentally bridging the organisation/execution divide without explicit design.
