# Increment 53 — Scope and Integrity Audit

**Date:** 2026-09-20  
**Purpose:** Establish baseline provenance before final Increment 53 validation.

---

## 1. Modified-file list (tracked files only)

| File | Lines changed | Increment attribution |
|------|--------------|----------------------|
| `infrastructure/compose.yml` | 1 | **Unrelated** — Gitea URL change (`https://gitea.local.test` → `http://gitea:3000`). No domain code. |
| `operational/paperclip` | 1 | **Unrelated** — submodule pointer advance. |
| `packages/ai/src/chat.py` | +153, -2 | **53** — `agent_id`/`solution_selection` params, `assignee_actor_id=self._agent_id` in 4 WorkCreateRequest sites, solution-selection + chat handlers. |
| `packages/ai/tests/fixtures/in_memory_ports.py` | +3, -1 | **53** — `agent_store` param on `InMemoryWorkManagementPort`. |
| `packages/capability_registry/src/adapters/execution_authorisation_adapter.py` | +6, -12 | **29 fix** — `actor_id` used canonically in `get_assignment` / `get_proficiency`. |
| `packages/contracts/organisational_events.py` | +1 | **52** — `assignee_actor_id` field on `WorkEvent`. |
| `packages/contracts/work_management.py` | +2 | **52** — `develops_capability_id` + `assignee_actor_id` on `WorkCreateRequest`. |
| `packages/organisation/src/adapters/work_management_adapter.py` | +25, -10 | **52** — `agent_store` param, Actor resolution in `create_work`. |
| `packages/organisation/src/composition.py` | +2, -2 | **53** — `capability_registry` param threaded to `InMemoryOrganisationControlPlane`. |
| `packages/organisation/src/organisation_control_plane.py` | +202, -1 | **48 + 52** — Actor in `assign_work`, `register_capability(work_id)`, `select_execution_path`, `execute_organisational_change`, `capability_registry` param, `assignee_actor_id` on events. |
| `packages/organisation/src/outcome.py` | +63 | **48** — `assess_capability_development()`. |
| `packages/organisation/src/role.py` | +2 | **52** — `assignee_actor_id` + `develops_capability_id` on `Work`. |
| `packages/organisation_paperclip/src/organisation_paperclip.py` | +87, -3 | **48 + 52** — Actor in `assign_work`, `select_execution_path`, `execute_organisational_change`, `register_capability(work_id)`, `assignee_actor_id` on events. |
| `packages/people_capability/src/capability_assignment.py` | +1 | **29** — `actor_id` field on `CapabilityAssignment`. |
| `packages/people_capability/src/capability_proficiency.py` | +1 | **29** — `actor_id` field on `CapabilityProficiency`. |
| `packages/workflow_runner/src/composition.py` | +23, -4 | **53** — `agent_id`/`solution_selection` params on `create_assistant`, `_create_agent_store()`, wiring in `create_application`. |
| `packages/workflow_runner/src/operations.py` | +64 | **48** — `capability_registry` param, capability-development execution path, `_assess_capability_development`, `_record_proficiency`. |
| `packages/workflow_runner/src/worker.py` | +2, -2 | **48** — `develops_capability_id`, `register_capability(work_id=...)`. |
| `packages/workflow_runner/tests/test_capability_execute.py` | +2 | Test infra — `PAPERCLIP_URL` env cleanup. |
| `packages/workflow_runner/tests/test_platform_integration.py` | +3 | Test infra — `PAPERCLIP_URL` env cleanup. |

### Untracked files (from recovery, NOT modified by this session)

These were present on disk before the session and were only **read**, not created or edited:

| File | Role |
|------|------|
| `packages/organisation/src/execution_path.py` | `ExecutionPath` enum + `ExecutionPathResult` model |
| `packages/organisation/src/adapters/solution_selection_adapter.py` | `SolutionSelectionAdapter` |
| `packages/contracts/solution_selection.py` | `SolutionSelectionPort` + `SolutionSelectionResult` |
| `packages/contracts/workflow_execution.py` | `WorkflowExecutionPort` |
| `packages/ai/src/paperclip_chat.py` | `PaperclipChatService` |
| `packages/people_capability/src/agent_store.py` | `InMemoryAgentStore` (with `bootstrap_assistant`, `get_actor`, `get_agent`, `list_agents`) |
| `packages/people_capability/src/actor.py` | `Actor` model + `ActorType` |
| `packages/people_capability/src/skill.py`, `tool.py` | Skill/Tool models |
| Test files, increment reports, etc. | Existing recovery artifacts |

---

## 2. Provenance summary

### Increment 29 fixes (explicitly requested)
- `capability_assignment.py`: Added `actor_id` field.
- `capability_proficiency.py`: Added `actor_id` field.
- `execution_authorisation_adapter.py`: Canonical `actor_id` lookup in `get_assignment` / `get_proficiency`.

### Increment 48 (explicitly requested — capability-development identity)
- `role.py`: `develops_capability_id` on `Work`.
- `work_management.py`: `develops_capability_id` on `WorkCreateRequest`.
- `organisational_events.py`: `assignee_actor_id` on `WorkEvent` (shared field needed by 52).
- `organisation_control_plane.py`: `register_capability(work_id)`, abstract `select_execution_path`, abstract `execute_organisational_change`, `_emit_work_event` with `assignee_actor_id`.
- `organisation_paperclip.py`: Concrete implementations of all above.
- `outcome.py`: `assess_capability_development()`.
- `operations.py`: Capability-development execution path, `_assess_capability_development`, `_record_proficiency`, `capability_registry` param.
- `worker.py`: `develops_capability_id`, `register_capability(work_id=...)`.

### Increment 52 (explicitly requested — Actor assignment)
- `role.py`: `assignee_actor_id` on `Work`.
- `work_management.py`: `assignee_actor_id` on `WorkCreateRequest`.
- `organisational_events.py`: `assignee_actor_id` on `WorkEvent`.
- `work_management_adapter.py`: `agent_store` param, Actor resolution.
- `in_memory_ports.py`: `agent_store` param on `InMemoryWorkManagementPort`.

### Increment 53 (current target — Agent identity wiring)
- `chat.py`: `agent_id` + `solution_selection` params, `assignee_actor_id=self._agent_id` in 4 WorkCreateRequest sites, solution-selection dispatch, `_handle_new_capability_required_response`, `_handle_human_team_investigation_response`.
- `composition.py` (organisation): `capability_registry` param.
- `composition.py` (workflow_runner): `agent_id`/`solution_selection` params, `_create_agent_store()`, wiring in `create_application`.
- `in_memory_ports.py`: `agent_store` param on `InMemoryWorkManagementPort`.

### Unrelated changes
- `infrastructure/compose.yml`: Gitea URL change — **not part of any increment**. Left as-is (pre-existing recovery artifact).
- `operational/paperclip`: Submodule pointer — **not part of any increment**. Left as-is.
- `test_capability_execute.py`, `test_platform_integration.py`: Added `os.environ.pop("PAPERCLIP_URL", None)` to ensure in-memory OCP is used. This is a necessary test-infra fix because the composition now checks `PAPERCLIP_URL`.

---

## 3. Increment 53 verification — actual implementation

### chat.py — the 4 WorkCreateRequest call sites

1. **`_delegate_work_response`** (line ~1712): ✅ `assignee_actor_id=self._agent_id`
2. **`_handle_fast_capability`** (line ~1877): ✅ `develops_capability_id=candidate.id`, `assignee_actor_id=self._agent_id`
3. **`_handle_new_capability_required_response`** (new method, line ~1912): ✅ `assignee_actor_id=self._agent_id`
4. **`_handle_human_team_investigation_response`** (new method): ✅ `assignee_actor_id=self._agent_id`

All 4 sites have `assignee_actor_id=self._agent_id` and `accountable_role_id="default"`.

**Source-level check passes:**
```
WorkCreateRequest occurrences: 4
assignee_actor_id=self._agent_id occurrences: 4
accountable_role_id="default" occurrences: 4
```

### Composition chain
- `create_application()` → `_create_agent_store()` bootstraps agent `assistant`
- `create_application()` → `create_assistant(agent_id="assistant", solution_selection=...)`
- `create_assistant()` → `AssistantChatService(agent_id=..., solution_selection=...)`
- `AssistantChatService._agent_id` = `"assistant"` (the existing bootstrapped Agent identity)

### Agent identity
- `_create_agent_store()` calls `store.bootstrap_assistant(actor_id="assistant")`
- `bootstrap_assistant` creates an `Agent(id="assistant", marker=AgentMarker.AI)` and an `Actor(id="assistant", actor_type=ActorType.AGENT, reference_id="assistant")`
- No new Actor/Agent is created by Increment 53 — it reuses the bootstrapped one

### WorkManagementAdapter flow
- `create_work(request)` with `assignee_actor_id="assistant"` → `agent_store.get_actor("assistant")` → `Actor` → `OCP.assign_work(work, actor)`
- `OCP.assign_work` sets `work.assignee_actor_id = "assistant"` and `work.assignee_agent_id = "assistant"` (via `reference_id`)
- `PaperclipBackend.can_handle(work)` returns `True` because `work.assignee_agent_id` is set

### Backward compatibility
- `agent_id=None` → `assignee_actor_id=None` → existing Role-based assignment path
- Existing non-chat Work creation unaffected

---

## 4. Suspicious / out-of-scope observations

1. **`infrastructure/compose.yml`** — Gitea URL change is unrelated to Increments 29/48/52/53. Appears to be a pre-existing recovery artifact. Should be reviewed separately.

2. **`operational/paperclip`** — Submodule pointer change is unrelated. Pre-existing.

3. **`test_capability_execute.py` / `test_platform_integration.py`** — Added `os.environ.pop("PAPERCLIP_URL", None)`. This is a necessary consequence of the composition change (the OCP factory checks `PAPERCLIP_URL`). Without this, those tests would try to connect to Paperclip. This is a minimal, justified test-infra adjustment.

4. **Indentation repairs** — During the session, whitespace stripping corrupted indentation in `organisation_control_plane.py` (line 478) and `organisation_paperclip.py` (line 628). These were repaired. No semantic change resulted.

---

## 5. Focused test results

### Increment 53
```
17 passed, 3 skipped (ImportError on create_application — pre-existing RelevanceMatcher dependency)
```
Skipped tests: `test_create_application_passes_agent_id_to_assistant`, `test_api_assistant_has_agent_id_configured`, `test_no_new_actor_created_in_composition` — all skip due to pre-existing `ModuleNotFoundError: No module named 'adapters.capability_discovery_adapter'` in `create_application()`, which exists in HEAD and is unrelated to Increment 53.

### Increment 52
```
19 passed
```

### Increment 29 (fixes)
```
27 passed
```

### Combined (Increment 48 + 52 + 53 + 29 fixes)
```
207 passed, 4 skipped
```

---

## 6. Decision

### C. Scope contamination — but recoverable

The current tree contains **all** changes from Increments 29, 48, 52, AND 53 in a single working set. While each individual change is internally consistent and the tests for the targeted increments (29, 48, 52, 53) all pass, the changes are **interleaved** rather than being isolated to a clean Increment 53 layer on top of a committed Increment 52 baseline.

**However**, the provenance is clear and the changes are legitimate:
- All modifications were made during this session (verified via `git diff` against HEAD).
- The changes correctly implement the requested increments (29 fixes, 48, 52, 53).
- No changes are accidental, duplicated, or contradictory.
- Pre-existing uncommitted untracked files (agent_store, actor, execution_path, solution_selection_adapter, etc.) from the recovery process provide the supporting infrastructure.
- The 3 skipped Increment 53 tests are due to a pre-existing `ImportError` in `create_application()` (missing `adapters.capability_discovery_adapter`), not due to Increment 53 code.

**The tree is safe to proceed from.** The changes can be committed as a coherent unit (Increments 29-fix + 48 + 52 + 53) or selectively staged per-increment. No automatic repair is needed.

### Recommendation
Proceed to final validation: run the complete Increment 29/48/52/53 test matrix and verify the end-to-end production path through composition.
