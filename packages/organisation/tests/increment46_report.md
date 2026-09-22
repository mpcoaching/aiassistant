# Increment 46 — Capability Gap → People Boundary: Investigation Report

## Objective

Investigate the `NEW_CAPABILITY_REQUIRED` path (OCP → chat layer → Work creation → Worker capability development → assessment) and determine the minimum coherent boundary by which a capability gap becomes an actionable organisational requirement, using primitives established in Increments 40–45.

Determine whether `capability_id` (from `ExecutionPathResult`) is propagated as actionable identity through the full capability-development lifecycle, or whether the gap identity is lost and a new synthetic ID (`cap-{work.id}`) replaces it.

Determine whether `CapabilityEventType.DEVELOPMENT_STARTED` and `DEVELOPMENT_COMPLETED` should be emitted and whether their absence constitutes a semantic defect.

Determine whether `record_work_learning` correctly excludes `capability_development` work from EIMS knowledge capture.

No production code changes were made. All findings are documented as READ-ONLY observations.

---

## 1. Capability Gap Flow — Traced from Code

### 1.1 Decision Hierarchy (OCP)

`InMemoryOrganisationControlPlane.select_execution_path()` (`organisation_control_plane.py:544-626`):

| Priority | Condition | Path | capability_id |
|----------|-----------|------|---------------|
| 1 | `workflow_lookup(intent)` returns matches | `EXISTING_WORKFLOW` | None |
| 2 | `required_capability_ids` contains a capability in registry OR `candidate_capabilities` match; `capability_query` returns available | `CAPABILITY_PATH` | the capability_id |
| 3 | Capability exists in registry but `capability_query` returns `available=False` | `HUMAN_TEAM_INVESTIGATION` | the capability_id |
| 4 | `candidates` list is empty (no matching workflow, no matching capability) | `NEW_CAPABILITY_REQUIRED` | None |
| 5 | `candidates` non-empty, `capability_query` returns `None` (unknown) | `NEW_CAPABILITY_REQUIRED` | the capability_id |

**Key finding (Defect D1):** When a `required_capability_id` is unknown to the registry and NOT present in `candidate_capabilities`, it is silently dropped — the `candidates` list never includes it, and OCP falls through to the final `NEW_CAPABILITY_REQUIRED` with `capability_id=None`. The missing capability ID is lost.

```python
# organisation_control_plane.py:574-586
candidates: list[str] = []
for cap_id in required_capabilities:
    capability = self.get_capability(cap_id)   # Returns None for unknown caps
    if capability is None:
        for cand in candidate_capabilities:     # Only checks candidates already in context
            ...
    if capability is not None and cap_id not in candidates:
        candidates.append(cap_id)               # cap_id NOT added if get_capability() returned None
```

A required capability that is NOT in the registry AND NOT in `candidate_capabilities` is never queried and its ID is dropped from the result. The path only carries `capability_id` when the capability was found in `candidate_capabilities` (and then the query port returns `None`).

### 1.2 Chat Layer — Work Creation

`chat.py:851-871` dispatches based on `path_result.path`:

- `new_capability_required` → `_handle_new_capability_required_response()`
- `human_team_investigation` → `_handle_human_team_investigation_response()`
- `capability_path` → `_handle_capability_path_response()`

### 1.3 Two Entry Points Create Equivalent Work

| Entry Point | Method (chat.py) | capability_id available? | Propagated to Work? |
|-------------|------------------|--------------------------|---------------------|
| `NEW_CAPABILITY_REQUIRED` from OCP | `_handle_new_capability_required_response` (line 1647) | `path_result.capability_id` (line 1656) | **NO** — hardcoded `[]` (line 1673) |
| Capability gap from `_evaluate_enterprise_action` | `_handle_capability_gap` (line 1850) | `candidate.id` (line 1855) | **NO** — hardcoded `[]` (line 1868) |
| `HUMAN_TEAM_INVESTIGATION` (for contrast) | `_handle_human_team_investigation_response` (line 1696) | `path_result.capability_id` (line 1705) | **YES** — `[capability_id] if capability_id else []` (line 1725) |

**Key finding (Defect D2):** Both capability-development Work creation paths set `required_capability_ids=[]` on the `WorkCreateRequest`, discarding the `capability_id` from the path result. This is inconsistent with `_handle_human_team_investigation_response`, which does propagate it.

```python
# chat.py:1665-1674 (NEW_CAPABILITY_REQUIRED)
work_ref = self._work_management.create_work(
    WorkCreateRequest(
        ...
        work_type="capability_development",
        ...
        required_capability_ids=[],  # ← capability_id discarded
    )
)

# chat.py:1860-1869 (_handle_capability_gap)
work_ref = self._work_management.create_work(
    WorkCreateRequest(
        ...
        work_type="capability_development",
        ...
        required_capability_ids=[],  # ← candidate.id discarded
    )
)

# chat.py:1717-1726 (HUMAN_TEAM_INVESTIGATION — for contrast)
work_ref = self._work_management.create_work(
    WorkCreateRequest(
        ...
        required_capability_ids=[capability_id] if capability_id else [],  # ← propagated
    )
)
```

### 1.4 Work Management Adapter

`work_management_adapter.py:22-42`: Maps `WorkCreateRequest` → `Work` model, including `required_capability_ids=list(request.required_capability_ids)`. The adapter faithfully copies whatever it receives — if the chat layer sends `[]`, the Work has `[]`.

### 1.5 Worker — Capability ID Generation

`worker.py:115-151`: `_develop_capability` generates the capability ID as `f"cap-{work.id}"`:

```python
# worker.py:119
capability_id = f"cap-{work.id}"
```

**Key finding (Defect D3):** The original `capability_id` from the path result is completely discarded. The Worker synthesizes a new ID from the Work ID. There is no mechanism to recover the original capability identity. Even if `required_capability_ids` were populated on the Work, the Worker does not read it — it always generates `cap-{work.id}`.

### 1.6 Capability Registration

`worker.py:135-138`: When `_capability_registry` is available, the Worker calls `self._capability_registry.register(capability)`. Otherwise it falls back to `org_plane.register_capability(capability)`.

`organisation_control_plane.py:448-473`: `register_capability` delegates to the injected registry if available, otherwise stores locally. In both cases, it emits a `CapabilityEvent` with `event_type="capability.registered"`.

**Key finding (Defect D4):** Only `REGISTERED` events are emitted. `DEVELOPMENT_STARTED` is never emitted (even when development begins), and `DEVELOPMENT_COMPLETED` is never emitted (even when assessment passes). The enum values exist in `CapabilityEventType` but have zero emitters in production code.

### 1.7 Operations — Assessment

`operations.py:201-234`: After Work completion, `_assess_capability_development` is called. It:

1. Returns early if `self._capability_registry is None` (line 208-209)
2. Retrieves `capability_id` from `result.get("capability_id")` — this is the Worker-generated `cap-{work.id}` (line 211)
3. Fetches the capability from the registry (line 215)
4. Calls `assess_capability_development()` from `outcome.py` (line 221)
5. If assessment passes, calls `self._capability_registry.promote(capability_id)` (line 228)

**Key finding (Defect D5):** If `self._capability_registry` is `None` (which happens in the default Worker construction path — see `worker.py:36`), the entire assessment/proficiency pipeline is skipped. The capability remains in `DRAFT` status with no promotion to `ACTIVE` and no proficiency recording.

### 1.8 record_work_learning Exclusion

`outcome.py:66-110`: `record_work_learning` only records Work with `work_type in ("project", "initiative")`:

```python
# outcome.py:83
if work.work_type not in ("project", "initiative"):
    return None
```

**Key finding (Decision A1):** `capability_development` work is explicitly excluded from EIMS knowledge capture. The capability's interface and execution result are assessed via `assess_capability_development()` (which returns evidence), but this evidence is not stored as a durable `EnterpriseConcept` in the knowledge store. Only project/initiative outcomes become `SOLVED_APPROACH` concepts.

---

## 2. Minimum Coherent Boundary Analysis

### 2.1 Current Gap

The current flow has a **coherence gap** between the capability gap detection and the capability identity that ends up in the registry. Here's the path:

```
User intent
    → OCP.select_execution_path → ExecutionPathResult{path=NEW_CAPABILITY_REQUIRED, capability_id="cap-original"}
    → chat._handle_new_capability_required_response → WorkCreateRequest(required_capability_ids=[])
    → WorkManagementAdapter → Work(required_capability_ids=[])
    → Worker._develop_capability → Capability(id="cap-{work.id}")  ← original ID lost
    → CapabilityRegistry.register(capability) → CapabilityEvent(REGISTERED)
    → Operations._assess_capability_development → promote() → CapabilityEvent(?)
```

The `capability_id` from the original gap identification is:
1. Carried by `ExecutionPathResult` but **not propagated** to `WorkCreateRequest`
2. If it were propagated to `Work.required_capability_ids`, it would be semantically wrong — `required_capability_ids` means "capabilities REQUIRED to perform this Work", not "the capability being developed"
3. The Worker **ignores** `required_capability_ids` and generates `cap-{work.id}` regardless

### 2.2 Semantic Model of required_capability_ids

Per `role.py:116`: `required_capability_ids: list[str]` with the docstring from `INCREMENT-21W` defining `work.created` origin as WorkManagement and `work.assigned` as WorkManagement. The field semantic is: "capabilities required to execute this Work".

For a `capability_development` work item, the Work itself IS the development effort. It doesn't "require" the capability it's developing (that would be circular). So `required_capability_ids=[]` is semantically correct for the Work object.

The original gap `capability_id` needs a **different field** to carry it — such as `Work.metadata` or a dedicated `developing_capability_id` field. But currently no such field exists, and the chat layer doesn't set any.

### 2.3 The cap-{work.id} Identity

The Worker's `cap-{work.id}` pattern means:
- The developed capability has a synthetic ID derived from its development Work
- There is **no traceability** from the developed capability back to the original capability ID that triggered the gap
- `test_organisational_learning_loop_via_api` (test_capability_execute.py:817) explicitly asserts `developed_cap_id == f"cap-{work_id}"`, baking this behavior into tests

---

## 3. DEVELOPMENT_STARTED / DEVELOPMENT_COMPLETED Events

### 3.1 Current State

`CapabilityEventType` enum (`organisational_events.py:59-63`) defines:

```python
class CapabilityEventType(str, Enum):
    DEVELOPMENT_STARTED = "capability.development.started"
    DEVELOPMENT_COMPLETED = "capability.development.completed"
    REGISTERED = "capability.registered"
    BOTTLENECK_DETECTED = "capability.bottleneck.detected"
```

### 3.2 Emission Audit

| Event Type | Emitted From | In Production? |
|------------|-------------|-----------------|
| `REGISTERED` | `register_capability()` in both InMemory OCP and Paperclip OCP | **YES** |
| `DEVELOPMENT_STARTED` | Nowhere | **NO** |
| `DEVELOPMENT_COMPLETED` | Nowhere | **NO** |
| `BOTTLENECK_DETECTED` | Nowhere (BottleneckSignal exists but is separate) | **NO** |

### 3.3 Test Coverage

`test_events.py:108-115` only tests that `CapabilityEvent` can be *constructed* with `DEVELOPMENT_COMPLETED` — it does not test emission. No production code emits these events.

### 3.4 Consumers

`Operations._handle_event` only processes `WorkEvent` with `WorkEventType.READY` (line 166). No production consumer processes `CapabilityEvent`.

---

## 4. record_work_learning Exclusion

`record_work_learning` (`outcome.py:66-110`):

- Returns `None` immediately if `work.work_type not in ("project", "initiative")` (line 83-84)
- Only records `SOLVED_APPROACH` EnterpriseConcepts for project/initiative work

**This is an intentional design decision (Decision A1):** capability_development work does not produce durable EIMS knowledge. The capability's interface and execution result are assessed by `assess_capability_development()` but that assessment evidence is:
1. Used by `Operations._assess_capability_development` for promotion/proficiency
2. NOT stored as a durable EnterpriseConcept in the knowledge store

This means: after a capability is developed and promoted, there is no record in EIMS of *why* the capability was needed, what the development work produced, or who developed it — only the Capability object itself carries this (in its `payload` and metadata fields).

---

## 5. Hypothesis Assessment

| # | Hypothesis | Verdict | Evidence |
|---|-----------|---------|----------|
| H1 | `capability_id` from `ExecutionPathResult.NEW_CAPABILITY_REQUIRED` is propagated to `Work.required_capability_ids` | **Rejected** | `_handle_new_capability_required_response` (chat.py:1673) hardcodes `required_capability_ids=[]`; `_handle_capability_gap` (chat.py:1868) also hardcodes `[]` |
| H2 | `required_capability_ids` is the semantically correct field for carrying the developed capability ID | **Rejected** | ADR-027 defines `required_capability_ids` as "capabilities required to perform this Work", NOT "capability being developed". For `capability_development` work, `required_capability_ids=[]` is correct |
| H3 | The original capability ID is preserved through the Worker's `cap-{work.id}` generation | **Rejected** | `_develop_capability` (worker.py:119) generates `cap-{work.id}`; no mechanism reads original capability_id from Work |
| H4 | `DEVELOPMENT_STARTED` / `DEVELOPMENT_COMPLETED` events should be emitted | **Open** | Events are defined but never emitted. No consumer exists, but their presence in the enum suggests intended use. Their absence does not break existing flows |
| H5 | `DEVELOPMENT_COMPLETED` should be emitted after `Operations._assess_capability_development` | **Open** | Assessment happens in `Operations` (line 201-234) but no `CapabilityEvent` is emitted. The assessment result (pass/fail, promotion) is internal to Operations |
| H6 | `record_work_learning` correctly excludes `capability_development` work | **Confirmed** | `outcome.py:83` checks `work.work_type not in ("project", "initiative")` — `capability_development` is excluded |
| H7 | The capability gap → capability development flow is traceable end-to-end | **Rejected** | Original capability_id is lost at chat.py→WorkCreateRequest boundary; Worker generates synthetic `cap-{work.id}`; no metadata link survives |
| H8 | Paperclip OCP provides capability_id in NEW_CAPABILITY_REQUIRED fallback | **Rejected** | Paperclip `select_execution_path` (line 511-539) returns `NEW_CAPABILITY_REQUIRED` with `capability_id=None` — it does not extract a specific gap ID |
| H9 | The capability_query=None case loses the required_capability_id | **Confirmed** | When a required capability is unknown to the registry and not in `candidate_capabilities`, the `candidates` list excludes it, and the final `NEW_CAPABILITY_REQUIRED` has `capability_id=None` |

---

## 6. Increment Decisions

### Decision 1 — No production changes (H1, H3, H7)

The `capability_id` from `path_result` is available in `_handle_new_capability_required_response` but is only used for the Work **title** (`f"Develop capability: {capability_id}"`), not for `required_capability_ids`. This is consistent with the semantic model: `required_capability_ids` means "capabilities required to perform this Work", not "the capability being developed".

The Worker's `cap-{work.id}` ID generation is a deliberate design: the developed capability's identity is derived from the development Work, not from the original gap detection. This is tested and asserted in `test_organisational_learning_loop_via_api`.

**To make the original capability_id traceable**, a new field would be needed (e.g., `Work.metadata["gap_capability_id"]` or a dedicated `developing_capability_id` field on Work). This is a schema change, not a defect fix.

### Decision 2 — DEVELOPMENT_STARTED / DEVELOPMENT_COMPLETED are unimplemented features, not defects (H4, H5)

The events are defined in the `CapabilityEventType` enum but have no emitters. This is consistent with the pattern in Increment 45 where `QUEUED`, `STARTED`, and `ESCALATED` WorkEventType values are also defined-but-unemitted.

**Recommendation for future implementation:** If these events are needed:
- `DEVELOPMENT_STARTED` should be emitted by `Operations._handle_event` when work with `work_type == "capability_development"` is picked up for execution (after READY event, before backend.execute)
- `DEVELOPMENT_COMPLETED` should be emitted by `Operations._assess_capability_development` after assessment and promotion, carrying the capability_id, work_id, and assessment result

No production code change is warranted at this time.

### Decision 3 — record_work_learning exclusion is intentional (H6)

`record_work_learning` excludes `capability_development` work from EIMS knowledge capture. This is a deliberate architectural decision: capability development produces Capability objects (tracked by CapabilityRegistry), not EnterpriseConcepts (tracked by EIMS/ConceptStore). The two knowledge systems serve different purposes.

### Decision 4 — Query port None case is a latent defect (H9)

When `capability_query` is provided and returns `None` for a capability that IS in the `candidates` list, `capability_id` is preserved in the result. But when a required capability is NOT in `candidates` (because it wasn't found in the registry or `candidate_capabilities`), the final fallback returns `capability_id=None`.

This is a **latent gap** in the capability gap identification flow: if a caller passes `required_capability_ids=["cap-x"]` but doesn't also populate `candidate_capabilities` with `{"id": "cap-x", ...}`, the OCP cannot produce a specific `capability_id` in the result. The ID is silently lost.

**Recommendation (non-urgent):** The final fallback return (line 623-626) could preserve `required_capabilities` in `metadata` for diagnostic purposes, even when `capability_id` is None. This would allow downstream consumers to know which capability IDs were requested but not matched.

---

## 7. Tests Written

File: `packages/organisation/tests/test_increment46_capability_gap_people_boundary.py` (29 tests, all passing)

### Test Summary by Area

| Area | Tests | Key Finding |
|------|-------|-------------|
| A. select_execution_path decision hierarchy | 6 | Decision hierarchy is correct; query-port None is treated as gap not unavailable |
| B. capability_id propagation to Work | 3 | `capability_id` is NOT propagated to `required_capability_ids` for capability_development work (confirmed as semantically correct); `HUMAN_TEAM_INVESTIGATION` DOES propagate (contrast) |
| C. Worker._develop_capability ID generation | 2 | Always generates `cap-{work.id}`; original capability_id is discarded |
| D. DEVELOPMENT_STARTED/COMPLETED events | 5 | Defined but never emitted from any production code |
| E. record_work_learning exclusion | 2 | `capability_development` work excluded; `project` work recorded (contrast) |
| F. CapabilityRegistry lifecycle ownership | 2 | Registry owns register/promote; OCP delegates when available |
| G. People/Capability boundary | 3 | OCP does not define Capability class; model lives in people_capability |
| H. Paperclip OCP select_execution_path | 1 | Paperclip returns `NEW_CAPABILITY_REQUIRED` with `capability_id=None` |
| I. SolutionSelectionAdapter propagation | 2 | Adapter source shows `capability_id=org_result.capability_id` propagation |
| J. Capability identity discontinuity | 2 | `cap-{work.id}` differs from original `capability_id`; registry receives generated ID |

---

## 8. Validation

```
$ python -m pytest packages/organisation/tests/test_increment46_capability_gap_people_boundary.py -v --tb=short
# 29 passed

$ python -m pytest packages/organisation/tests/test_increment30_capability_boundary.py -v --tb=short
# 32 passed (existing capability boundary tests still pass)

$ python -m pytest packages/organisation/tests/test_increment35_lifecycle_adoption.py -v --tb=short
# (existing tests still pass)

$ python -m ruff check packages/organisation/tests/test_increment46_capability_gap_people_boundary.py
# All clear (after auto-fix)
```

---

## 9. Files Investigated

- `packages/organisation/src/organisation_control_plane.py` — `select_execution_path` (lines 544–626), `register_capability` (lines 448–473)
- `packages/organisation_paperclip/src/organisation_paperclip.py` — `select_execution_path` (lines 511–539), `register_capability` (lines 436–455)
- `packages/organisation/src/execution_path.py` — `ExecutionPathResult` model (line 25), `ExecutionPath` enum (line 16)
- `packages/ai/src/chat.py` — `_handle_new_capability_required_response` (lines 1647–1694), `_handle_capability_gap` (lines 1850–1893), `_handle_human_team_investigation_response` (lines 1696–1742), dispatch in `chat()` (lines 851–871)
- `packages/organisation/src/adapters/work_management_adapter.py` — `create_work` (lines 22–42) translating `WorkCreateRequest` → `Work`
- `packages/organisation/src/adapters/solution_selection_adapter.py` — `select_execution_path` (lines 32–61) translating `ExecutionPathResult` → `SolutionSelectionResult`
- `packages/workflow_runner/src/operations.py` — `_handle_event` (lines 163–166), `_assess_capability_development` (lines 201–234), `_record_proficiency` (lines 236–269)
- `packages/workflow_runner/src/worker.py` — `execute` (lines 60–88), `_develop_capability` (lines 115–151)
- `packages/organisation/src/role.py` — `Work` model (line 96, `required_capability_ids` at line 116)
- `packages/organisation/src/outcome.py` — `assess_work_outcome` (lines 21–63), `record_work_learning` (lines 66–110, excludes `capability_development` at line 83), `assess_capability_development` (lines 113–204)
- `packages/people_capability/src/capability.py` — `Capability` model (line 43), `CapabilityStatus` enum (line 24)
- `packages/people_capability/src/actor.py` — `Actor` model (line 32), `ActorType` enum (line 25)
- `packages/people_capability/src/agent_store.py` — `InMemoryAgentStore` (line 27), `register_agent`/`register_person`/`assign_capability`
- `packages/capability_registry/src/capabilities.py` — `CapabilityRegistry` (line 22), `register` (line 30), `promote` (line 84)
- `packages/contracts/organisational_events.py` — `CapabilityEventType` enum (line 59), `CapabilityEvent` model (line 93), `WorkEventType` enum (line 47)
- `packages/contracts/solution_selection.py` — `SolutionSelectionResult` (line 6), `SolutionSelectionPort` (line 16)
- `packages/contracts/enterprise_capability_query.py` — `CapabilityAvailability` (line 6), `EnterpriseCapabilityQueryPort` (line 14)
- `packages/contracts/work_management.py` — `WorkCreateRequest` (line 5), `WorkReference` (line 17), `WorkManagementPort` (line 23)
- `packages/workflow_runner/tests/test_assistant_actor.py` — `test_full_learning_loop` (lines 198–256), Work construction patterns (lines 133–161, 212–221)
- `packages/workflow_runner/tests/test_capability_execute.py` — `test_organisational_learning_loop_via_api` (lines 772–854)
- `packages/workflow_runner/tests/test_platform_integration.py` — `test_innovation_path_creates_capability_development_work` (lines 894–944)
- `packages/organisation/tests/test_execution_path.py` — Existing `select_execution_path` tests
- `packages/organisation/tests/test_increment30_capability_boundary.py` — Capability ownership, registry delegation, lifecycle tests
- `packages/organisation/tests/test_increment35_lifecycle_adoption.py` — Paperclip OCP select_execution_path
- `packages/organisation/tests/test_increment38_execution_evidence_boundary.py` — Evidence boundary, `record_work_learning` exclusion
- `packages/organisation/tests/test_increment41_economic_organisation_boundary.py` — Traceability chain, creation authority
- `packages/organisation/tests/test_increment45_work_event_lifecycle.py` — Work event lifecycle (preceding increment)
- `packages/organisation/tests/increment45_report.md` — Investigation findings from Increment 45
