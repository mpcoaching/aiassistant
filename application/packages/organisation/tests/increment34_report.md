# Increment 34 — Evidence → Workflow Adoption Boundary

## Report

---

### A. Evidence sources and semantics

| Evidence | What it proves | What it does NOT prove |
|---|---|---|
| **Invocation** (`InvocationRecorder.record_invocation` → `ConceptStore.record_invocation`) | A capability was invoked and produced an outcome classified as `success`/`failure`/`not_executed` (via `CapabilityOutcomeAssessor`). | That the execution followed a repeatable *pattern*; that the organisation should treat it as a `WorkflowDefinition`; that the pattern is understood well enough to be documented. |
| **CapabilityProficiency** (`CapabilityProficiency.evidence` with `source_work_id`) | An Actor demonstrated a proficiency level for a specific Capability, with evidence linked to originating Work IDs. | That the same execution sequence should be reused as an organisational workflow; that the capability exercises in a stable combinatory pattern with other capabilities. |
| **Successful Work outcome** (`assess_work_outcome`) | The Work item's `acceptance_criteria` were met against the execution result. | That the underlying execution pattern is repeatable; that a workflow should be created. The acceptance criteria are per-Work, not per-pattern. |
| **EIMS EnterpriseConcept** (`record_work_learning` → `SOLVED_APPROACH`) | An organisational concept was documented for durable enterprise value (project/initiative work only). | That an execution pattern should become a `WorkflowDefinition`. `record_work_learning` only records for `work_type` in `("project", "initiative")` — BAU work produces no EIMS record. |
| **Acceptance criteria** (`Work.acceptance_criteria`) | The organisational intent for a specific Work item was or was not satisfied. | That the approach should be standardised into a reusable workflow. Criteria are Work-scoped, not pattern-scoped. |
| **Multiple successful executions** (`MaturationHistory.invocation_count`, `correction_count`) | A capability has been invoked N times with M corrections — a usage statistic. | That a workflow should be created. `CapabilityRegistry.promote()` promotes a *capability* to `ACTIVE` status based on invocation statistics, but has no relationship to `WorkflowDefinition`. |

---

### B. What successful execution actually proves

Repeated successful execution of a capability (via `CapabilityExecutionPort.execute`) proves:

1. The capability can be exercised successfully — but **not** that the *combination* of steps constitutes a stable pattern.
2. The capability is available and functioning — but **not** that the organisation should adopt a workflow around it.

The architecture explicitly distinguishes four categories:

- **Repeated success caused by coincidence** — `MaturationHistory` records invocation_count, but there is no deduplication or pattern analysis. The same capability invoked 100 times with different contexts is indistinguishable from 100 identical-pattern invocations.
- **Repeated execution of essentially the same pattern** — The architecture has no mechanism to recognise this. `InvocationRecorder` records `capability_id` only, not the full execution graph or step sequence.
- **A stable execution pattern producing the same type of outcome** — `Work.outcome` and `assess_work_outcome` record per-Work results against acceptance criteria, but do not aggregate across Works.
- **An execution pattern understood well enough to be deliberately specified** — This is the point at which a `WorkflowDefinition` YAML file must be **written by a human**. No automatic mechanism exists.
- **An execution pattern the organisation has explicitly decided should become BAU** — This is an organisational decision that must be made **outside** the current code. No port, service, or entity represents this decision.

**Conclusion**: successful execution × N is **not sufficient**. The architecture requires explicit human organisational understanding and decision between evidence and adoption.

---

### C. Repetition vs repeatability vs understanding

The architecture has **no entity** bridging "observed execution" and "understood reusable pattern." There is:

- `Work` (organisational record of effort)
- `InvocationRecorder` / `ConceptStore` (telemetry of capability invocations)
- `Work.outcome` / `assess_work_outcome` (acceptance criteria evaluation)
- `CapabilityProficiency` (actor-level proficiency with evidence)
- `WorkflowDefinition` (explicit, declarative pattern)

There is **no** entity between "execution evidence" and "WorkflowDefinition." The gap is:

```
observed execution
    ↓  (no bridge: understanding is a human decision)
explicit pattern (WorkflowDefinition YAML, written by human)
    ↓  (no bridge: adoption is a human decision)
organisational adoption (filesystem presence + OCP recognition)
    ↓  (workflow_lookup callback searches filesystem)
EXISTING_WORKFLOW recognition by OCP
```

**Investigation finding**: "Understanding" should **not** be a new domain entity. It is a **decision/process boundary** — the moment a human writes a `WorkflowDefinition` YAML file, that act *is* the understanding crystallised into an explicit description. Creating a "Learning" or "Understanding" entity would be premature architecture (explicitly rejected by this increment's constraints).

---

### D. Adoption decision boundary

Where does the decision to adopt a workflow live?

1. **OCP directly** — OCP has `select_execution_path` which can return `EXISTING_WORKFLOW`. But OCP has **no** `adopt_workflow`, `register_workflow`, `compile_workflow`, or `create_workflow` method. OCP only **discovers** existing workflows; it does not create or adopt them.

2. **A future organisational learning/adoption service** — Does not exist. Would be the natural home for the adoption decision (a future Increment).

3. **A domain port owned by organisation** — Does not exist. No `WorkflowAdoptionPort` in `contracts/`.

4. **Some other existing organisational boundary** — The closest existing mechanism is `record_work_learning` → `SOLVED_APPROACH` in EIMS, and `CapabilityRegistry.promote()`. Neither creates or adopts `WorkflowDefinition` objects.

**Current state**: Workflow adoption is currently a **manual, external decision**. A human writes the YAML file to `agentic/docs/workflows/`, and OCP discovers it via `build_workflow_lookup`. There is no programmatic adoption boundary.

**Required boundary correction**: A `WorkflowAdoptionPort` (or equivalent decision service) should eventually live in the organisation plane. It would accept a `WorkflowDefinition` (or candidate pattern) and make the organisational decision to persist it to the workflow filesystem. Until then, the boundary is: **human writes YAML → filesystem → OCP discovers via `workflow_lookup`**.

---

### E. Minimum adoption contract

The smallest possible contract for workflow adoption would be:

```
candidate pattern (WorkflowDefinition)
    ↓
organisational decision (human/system)
    ↓
adopted workflow (persisted to filesystem)
```

Candidate fields for an adoption decision record:

| Field | Architecturally necessary? | Why |
|---|---|---|
| `workflow_definition` (the pattern itself) | **Yes** — must be the explicit definition |
| `rationale` (why adopted) | **Yes** — organisation needs to justify BAU |
| `source_work_ids` (which Work items informed it) | **Optional** — useful for traceability but not required for the boundary |
| `capability_ids` (what capabilities it exercises) | **No** — WorkflowDefinition steps already reference skills/tools by name |
| `author/actor` (who decided) | **Yes** — accountability for organisational decision |
| `approved_by` (who approved) | **Yes** — adoption is an organisational decision |
| `confidence` (0.0–1.0 certainty) | **No** — subjective; can remain in rationale text |
| `provenance` (how it came to exist) | **No** — see section F |
| `version` (adoption version) | **No** — see section M |
| `constraints` (when it applies) | **Optional** — can be part of rationale |

**Conclusion**: The minimum adoption contract needs: `workflow_definition`, `author`, `approved_by`, `rationale`. All other fields are either derivable or optional. However, since no adoption mechanism currently exists, this contract is **not required for the current architecture** — the human writes YAML directly.

---

### F. WorkflowDefinition provenance

Currently: **WorkflowDefinition has no provenance.**

The `WorkflowDefinition` model (`packages/workflow_runner/models.py:33`) has:
- `version: str` — schema version (`"1"`), not adoption lineage
- `name`, `description`, `kind`, `role`, `intent`, `inputs`, `outputs`, `steps`

There is no:
- `source_work_ids`
- `rationale`
- `author`
- `approved_by`
- `provenance`

The architecture **cannot answer** "Why does this WorkflowDefinition exist?" because:
1. No adoption decision record exists
2. The YAML file is the only artifact, with no metadata about its origin

**Is provenance required now?** — Not for the current architecture, because the adoption boundary itself does not exist programmatically. The question "why does this workflow exist?" is answered by **a human reading the YAML file's `description` field and checking the filesystem/git history**. Provenance becomes necessary when adoption is automated or when the organisation needs to distinguish "written by someone" from "adopted after successful executions."

**Smallest possible representation** (future): add an optional `provenance` dict to `WorkflowDefinition` that an adoption service could populate with `source_work_ids` and `rationale`. But this must come with the adoption service, not be added speculatively.

---

### G. Workflow creation/storage boundary

Workflow creation is currently:

```
Organisation decision (human writes YAML)
    ↓
Filesystem (agentic/docs/workflows/*.yaml)
    ↓
Loader (load_workflow / resolve_workflow_path)
    ↓
WorkflowExecutionPort (WorkflowExecutionAdapter.execute_workflow)
```

There is **no creation port** in `contracts/`. The `create_workflow` API endpoint (`api.py:286`) writes YAML to the filesystem — it is an API-level convenience, not an organisational decision boundary.

**Conclusion**: The existing filesystem/YAML mechanism is sufficient for the current architecture. A `WorkflowCreationPort` or `WorkflowAdoptionPort` would only be needed when the adoption decision is automated or mediated by the organisation plane (a future Increment).

---

### H. Workflow lookup / discoverability

- `build_workflow_lookup` (`composition.py:80`) builds a callable that searches YAML files in `agentic/docs/workflows` and `agentic/workflows`, matching by name/description keyword similarity to the intent string.
- `resolve_workflow_path` (`loader.py:232`) resolves a workflow name to a filesystem path.
- `WorkflowExecutionAdapter.execute_workflow` (`workflow_execution_adapter.py:27`) calls `resolve_workflow_path` then `execute_workflow_from_file`.
- `OCP.select_execution_path` receives `workflow_lookup` as a **callback** — it calls this callback with the intent string, and if it returns results, returns `EXISTING_WORKFLOW`.

**Key finding**: There is a **conflation between discoverability and adoption**. A workflow is "discoverable" iff it exists as a YAML file on the filesystem. OCP treats filesystem presence as the sole criterion for `EXISTING_WORKFLOW`. There is no "adopted" status — every YAML file in the workflows directory is treated as a valid, organisational workflow.

**Smallest boundary correction**: This conflation is **acceptable for the current architecture** because the YAML files are written by humans (the organisational decision is external). When the adoption decision becomes programmatic, a status field (`adopted: bool` or similar) would need to distinguish "proposed" from "approved." But introducing this now would be premature.

---

### I. Capability ↔ Workflow relationship

**How does OCP know an existing workflow is relevant to the requested capability/outcome?**

Currently: **It doesn't.** OCP's `select_execution_path` matches workflows by **intent string** (name/description keyword matching via `build_workflow_lookup`). There is:

- No `capability_id` on `WorkflowDefinition`
- No `capability_ids` list on `WorkflowDefinition`
- No method in OCP to associate a workflow with capabilities
- The `workflow_lookup` callback matches by intent text, not by capability requirements

**Is this sufficient?** — For the current architecture, yes. The intent string is meant to capture the user's request, and the workflow's name/description are meant to describe what it does. If they match textually, OCP assumes relevance. However, this is a **gap**: there is no organisational metadata linking a workflow to the capabilities/outcomes it supports. An organisation might need to know "this workflow exercises capabilities A, B, C" for compliance, capacity planning, or skill assignment purposes.

**Do not add `capability_id` to `WorkflowDefinition`** — the investigation confirms this is not required for the boundary. The capability↔workflow association belongs to the future adoption decision, not to the execution pattern definition itself.

---

### J. Skill ↔ Workflow relationship

**Does evidence of successful Skill execution create a WorkflowDefinition?**

No. The architecture keeps these completely separate:

- **Skill** (`people_capability/src/skill.py:22`): `id`, `capability_id`, `name`, `method`, `tool_ids` — a reusable method for exercising a Capability. No step structure.
- **WorkflowDefinition** (`workflow_runner/models.py:33`): `name`, `steps`, `inputs`, `outputs`, `intent` — an explicit, ordered orchestration pattern. Steps reference skills/tools workflows by string name.

A Skill may remain a reusable method forever without ever becoming a workflow. The architecture has **no** mechanism that says "N successful skill executions → create workflow." `CapabilityRegistry.promote()` promotes a capability's status (DRAFT → ACTIVE), not a skill-to-workflow transformation.

**Conclusion**: repeated Skill success does **not** create a Workflow. A Skill remains a reusable method; a Workflow is a separate, explicitly-authored pattern that *may* invoke skills.

---

### K. BAU transition

The complete conceptual transition:

```
UNCERTAIN
   ↓  [organisational: define Work, assign Role]
   Work  (role.py: Work)
   ↓  [organisational: mark_work_ready]
   Capability exercise  (or pattern invocation)
   ↓  [operational: Worker/Paperclip execute via ports]
   Evidence
      - InvocationRecorder → ConceptStore.MaturationHistory
      - Work.outcome
      - CapabilityProficiency
   ↓  [ORGANISATIONAL DECISION — currently manual/external]
   Understanding
      (no entity — crystallised when human writes WorkflowDefinition YAML)
   ↓  [ORGANISATIONAL DECISION — currently manual/external]
   Adoption decision
      (no entity/port — human writes YAML to agentic/docs/workflows/)
   ↓  [technical: load_workflow reads YAML]
   WorkflowDefinition  (workflow_runner/models.py: WorkflowDefinition)
   ↓  [organisational: OCP.select_execution_path via workflow_lookup]
   EXISTING_WORKFLOW  (ExecutionPath.EXISTING_WORKFLOW)
   ↓  [operational: WorkflowExecutionPort.execute_workflow]
   BAU
   ↓  [operational: WorkflowState tracks execution]
   WorkflowState  (workflow_runner/models.py: WorkflowState)
   ↓  [organisational: complete_work records Work.outcome]
   Work/outcome  (role.py: Work.outcome)
   ↓  [operational/evidential: InvocationRecorder, assess_work_outcome]
   Evidence
```

**Transition classification**:

| Transition | Type |
|---|---|
| UNCERTAIN → Work | Organisational decision |
| Work → Capability exercise | Operational execution (Worker, Paperclip) |
| Capability exercise → Evidence | Operational mechanism (InvocationRecorder, ConceptStore) |
| Evidence → Understanding | **Organisational decision** (currently external/manual) |
| Understanding → Adoption decision | **Organisational decision** (currently external/manual) |
| Adoption → WorkflowDefinition | Technical storage (filesystem YAML) |
| WorkflowDefinition → EXISTING_WORKFLOW | Organisational decision (OCP.select_execution_path) |
| EXISTING_WORKFLOW → BAU | Operational execution (WorkflowExecutionPort) |
| BAU → WorkflowState | Operational mechanism (executor, db.py) |
| WorkflowState → Work/outcome | Operational mechanism (complete_work) |
| Work/outcome → Evidence | Operational mechanism (InvocationRecorder, assess_work_outcome) |

**Key insight**: The two "organisational decision" transitions (Evidence → Understanding, Understanding → Adoption) are the **architectural seam** that is currently **unprogrammed**. Everything else has a technical mechanism. These two transitions require a human decision today.

---

### L. Failure feedback

```
BAU
  ↓  [operational: workflow execution fails]
workflow execution
  ↓  [operational: WorkflowState records status='failed', error=...]
failure / unexpected outcome
  ↓  [organisational: complete_work/fail_work records Work.outcome]
Work.outcome / execution evidence
  ↓  [organisational learning — currently external/manual]
organisational learning
  ↓  [organisational decision — currently external/manual]
pattern may need revision
  ↓  [technical: human rewrites YAML WorkflowDefinition]
WorkflowDefinition version/change
  ↓  [operational: OCP discovers new version via workflow_lookup]
BAU
```

**Can the existing architecture represent this conceptually?** — **Yes, partially**:

- `WorkflowState` records execution failures (`status="failed"`, `error="..."`)
- `Work.outcome` records the failure (via `fail_work`)
- `assess_work_outcome` classifies criteria met/failed
- `ConceptStore.record_invocation` records failures in `MaturationHistory.correction_count`
- `record_work_learning` records `SOLVED_APPROACH` for successful project/initiative work (but not failures)

**What is missing**: There is **no mechanism** for feedback from failure → workflow revision. A human must:
1. Observe the failure (via WorkflowState, Work.outcome)
2. Analyse the pattern's flaws
3. Rewrite the YAML file
4. The next OCP selection picks up the new version

The boundary that would eventually allow organisational learning to cause workflow revision:
- A `WorkflowRevisionPort` or `WorkflowAdoptionPort.update_workflow()` method
- A version/supersession field on `WorkflowDefinition`
- Currently: **no automatic or programmatic revision mechanism**

**No autonomous self-modifying workflows** — this is by design.

---

### M. Versioning / supersession

**WorkflowDefinition.version** field:
```python
version: str = Field(default="1", description="Schema version for future upgrades")
```

This is a **schema version** — it tracks the YAML format version, not adoption or lineage.

**Versioning gaps**:
- No `deprecated`/`deprecated_at` field — no way to mark a workflow as retired
- No `superseded_by`/`replaced_by` field — no way to point to a replacement
- No `status` field — no "draft" vs "active" vs "deprecated" lifecycle
- No version history — no way to track WorkflowDefinition v1 → v2 transition
- `ConceptStore.EnterpriseConcept` has `version_major`/`version_minor`/`version_patch` and `status` (draft/active/deprecated), but `WorkflowDefinition` is **not** stored as an `EnterpriseConcept` — it's a filesystem YAML file

**Conclusion**: `WorkflowDefinition.version` (schema version) is **not sufficient** for workflow adoption versioning. The smallest missing concepts are:
1. A `status` field (`active`/`deprecated`) on `WorkflowDefinition`
2. An optional `superseded_by` reference

However, adding these speculatively would be premature. The versioning boundary is not required until the adoption decision becomes programmatic.

---

### N. Architectural tests

Added **38 tests** in `packages/organisation/tests/test_increment34_evidence_adoption_boundary.py` covering:

| # | Test | Boundary proved |
|---|---|---|
| 1 | `test_invocation_recorder_records_telemetry_not_workflow_creation` | A. Invocation records telemetry, does not create WorkflowDefinition |
| 2 | `test_capability_proficiency_evidence_links_to_work_not_workflow` | A. Proficiency evidence links to Work, not to WorkflowDefinition |
| 3 | `test_successful_work_outcome_records_acceptance_not_adoption` | A. Work outcome = acceptance check, not adoption decision |
| 4 | `test_record_work_learning_records_solved_approach_not_workflow` | A. SOLVED_APPROACH documents solution, not workflow pattern |
| 5 | `test_maturation_history_tracks_invocations_not_workflow_adoption` | A. Invocation count ≠ workflow creation; ConceptStore has no workflow creation API |
| 6 | `test_repeated_successful_executions_do_not_create_workflow` | B. Frequency alone does not create workflow; compiler.py has compile_skill, not compile_workflow |
| 7 | `test_no_pattern_mining_or_extraction_module_exists` | B. No pattern_miner, workflow_synthesizer, workflow_compiler, etc. |
| 8 | `test_no_adoption_or_synthesis_function_in_any_module` | B. No adopt/synthesize/compile_workflow in any adoption-chain module |
| 9 | `test_workflow_definition_has_no_understanding_or_evidence_fields` | C. WorkflowDefinition has no evidence/understanding/confidence fields |
| 10 | `test_concept_store_has_no_workflow_creation_api` | C. ConceptStore (EIMS) has no workflow creation/adoption API |
| 11 | `test_ocp_has_no_workflow_creation_or_adoption_method` | D. OCP can discover but not create/adopt workflows |
| 12 | `test_ocp_select_execution_path_only_discovers_existing_workflows` | D. OCP only discovers filesystem workflows; capability with high invocation count is not returned as EXISTING_WORKFLOW |
| 13 | `test_workflow_execution_request_has_no_adoption_context` | E. WorkflowExecutionRequest has no adoption metadata |
| 14 | `test_workflow_execution_result_has_no_adoption_metadata` | E. WorkflowExecutionResult has no adoption metadata |
| 15 | `test_workflow_definition_has_no_provenance_fields` | F. No source_work_ids, author, approved_by, rationale, confidence |
| 16 | `test_workflow_definition_version_is_schema_not_adoption` | F. `version` is schema string "1", no deprecation/supersession |
| 17 | `test_workflow_creation_is_filesystem_not_organisational` | G. WorkflowExecutionAdapter loads from filesystem; does not create |
| 18 | `test_no_workflow_creation_port_in_contracts` | G. No WorkflowCreationPort or WorkflowAdoptionPort in contracts |
| 19 | `test_build_workflow_lookup_searches_filesystem_only` | H. lookup searches YAML by name/description; no adoption status |
| 20 | `test_workflow_lookup_matches_by_name_not_adoption_status` | H. Discovery is filesystem-based; no "adopted" flag |
| 21 | `test_workflow_loader_loads_yaml_not_adopts_from_evidence` | H. load_workflow reads YAML; does not synthesize from evidence |
| 22 | `test_workflow_definition_has_no_capability_id` | I. WorkflowDefinition has no capability_id; OCP matches by intent |
| 23 | `test_ocp_does_not_associate_workflows_with_capabilities` | I. OCP workflow lookup uses intent string matching, not capability association |
| 24 | `test_skill_has_no_workflow_steps` | J. Skill has no step structure; distinct from WorkflowDefinition |
| 25 | `test_capability_registry_has_no_workflow_methods` | J. CapabilityRegistry promotes capabilities, not workflows |
| 26 | `test_bau_work_execution_does_not_create_workflow` | K. Operations/Worker do not create WorkflowDefinitions |
| 27 | `test_workflow_execution_does_not_trigger_evidence_to_adoption` | K. WorkflowExecutionPort.execute_workflow has no adoption parameter |
| 28 | `test_failed_work_outcome_is_evidence_not_automatic_revision` | L. Failed Work outcome is evidence, not automatic workflow revision |
| 29 | `test_workflow_state_has_no_failure_feedback_to_definition` | L. WorkflowState and WorkflowDefinition are separate; failure doesn't modify definition |
| 30 | `test_workflow_definition_has_no_deprecation_or_supersession` | M. No status/deprecated/superseded_by/replaced_by fields |
| 31 | `test_workflow_definition_version_field_does_not_track_adoption_lineage` | M. `version` is schema not lineage; not a list |
| 32 | `test_invocation_recorder_does_not_create_workflow_definition` | N. record_invocation never creates WorkflowDefinition; ConceptStore source has no WorkflowDefinition construction |
| 33 | `test_no_synthesis_pipeline_from_evidence_to_workflow` | N. No code path from evidence to WorkflowDefinition creation (OCP, operations, worker) |
| 34 | `test_workflow_execution_adapter_has_no_adoption_methods` | N. WorkflowExecutionAdapter has only execute_workflow |
| 35 | `test_capability_execution_port_signature_has_no_workflow` | N. CapabilityExecutionPort.execute takes only capability_id/context/actor_context |
| 36 | `test_execution_result_does_not_contain_workflow_info` | N. ExecutionResult has no workflow fields |
| 37 | `test_workflow_lookup_callback_is_discovery_not_adoption` | N. workflow_lookup callback is discovery mechanism, not adoption check |
| 38 | `test_organisation_paperclip_backend_separate_from_workflow_adoption` | N. PaperclipBackend implements ExecutionBackend; no adoption methods |

---

### O. Code changes

**No code changes were required.** The investigation confirms that the architecture **correctly maintains** the evidence-to-adoption boundary: there is no mechanism that automatically turns evidence into workflows. All creation of `WorkflowDefinition` objects requires a human writing YAML. This is the correct design — the boundary is deliberately unprogrammed.

The only action taken: **added 38 architectural test** file at `packages/organisation/tests/test_increment34_evidence_adoption_boundary.py`.

---

### P. Required final model (smallest defensible)

```
Evidence
    ↓  (observational — InvocationRecorder, Work.outcome, CapabilityProficiency, MaturationHistory)
Understanding
    ↓  (decided externally by organisation — crystallised as WorkflowDefinition YAML)
Adoption
    ↓  (currently external — human writes YAML; future: WorkflowAdoptionPort)
WorkflowDefinition
```

**Do "Understanding" and "Adoption" need to be domain entities?**

**No.** They should remain **organisational decisions**, not entities:

- **Understanding** is crystallised when a human explicitly writes a `WorkflowDefinition` YAML file. The act of writing IS the understanding — no intermediate entity is needed.
- **Adoption** is crystallised when that YAML file exists in the workflows directory and OCP recognizes it via `workflow_lookup`. Filesystem presence IS the adoption signal in the current architecture.

Creating abstract "Understanding" or "Learning" entities would be premature architecture (explicitly rejected by section O).

**However**: when the adoption decision eventually becomes programmatic (an organisation wants to track "this workflow was adopted after N successful executions, reviewed by X, approved on date Y"), a `WorkflowAdoptionPort` interface and an optional `provenance` field on `WorkflowDefinition` would be the natural extension points. These are **not required now** because the current architecture deliberately externalises these decisions to humans.

---

### Q. Code changes

**None.** No implementation code was modified or added. The investigation confirmed the architecture already correctly leaves the evidence-to-adoption boundary unautomated.

**Only file added**: `packages/organisation/tests/test_increment34_evidence_adoption_boundary.py` (38 tests, all passing, ruff clean).

---

### R. Tests / results

```
packages/organisation/tests/test_increment34_evidence_adoption_boundary.py
  38 passed in 0.17s

Full suite (organisation + workflow_runner, excluding integration):
  616 passed (was 578 + 38 new)
  60 failed (pre-existing — all integration tests requiring external services)
  4 skipped
  0 regressions
```

Ruff: `All checks passed!` on the new test file.

---

### S. Pre-existing failures

The 60 pre-existing failures (unchanged from Increment 33 baseline) are all in:
- `packages/workflow_runner/tests/test_capability_execute.py` (10 tests)
- `packages/workflow_runner/tests/test_platform_integration.py` (50 tests)

These are **integration tests** marked with `@pytest.mark.integration` that require external services (Paperclip backend, AI provider, database). They are **not related** to the evidence-to-adoption boundary.

---

### T. Architectural gaps

1. **No WorkflowAdoptionPort** (`contracts/`) — There is no organisational port for deciding whether an observed pattern should become an adopted workflow. This is the central architectural gap: the evidence → understanding → adoption transition is entirely manual/external.

2. **No provenance on WorkflowDefinition** — `WorkflowDefinition` has no `source_work_ids`, `author`, `rationale`, or `approved_by`. The organisation cannot answer "why does this workflow exist?" or "who approved it?" without external git/history inspection.

3. **Filesystem presence = adoption** — `build_workflow_lookup` treats any YAML file in the workflows directory as a valid, adoptable workflow. There is no "proposed/draft/adopted" status. Any YAML file written to the directory immediately becomes discoverable by OCP.

4. **No capability↔workflow association** — `WorkflowDefinition` does not reference capabilities. OCP matches workflows to intents by name/description keyword search only, not by capability requirements.

5. **No versioning/supersession** — `WorkflowDefinition.version` is a schema version (`"1"`), not an adoption/semantic version. No `status`, `deprecated`, or `superseded_by` fields exist.

6. **No failure feedback to workflow revision** — A failed workflow execution records to `WorkflowState` and `Work.outcome`, but there is no mechanism to feed this back into revising the `WorkflowDefinition`. A human must manually update the YAML.

**All gaps are intentional** for the current architecture — they represent the boundaries between observation and organisational decision-making. They should remain unprogrammed until the organisation is ready to automate the adoption decision (a future increment).

---

### U. Recommended Increment 35

**Increment 35 — Workflow Adoption Decision Port**

Objective: Establish the minimal programmatic boundary for the organisational adoption decision, WITHOUT building synthesis, generation, or automation.

Tasks:

1. **Investigate**: What is the smallest organisational port that represents "the organisation has decided this pattern is a standard"?
2. **Design**: `WorkflowAdoptionPort` protocol in `contracts/` with:
   - `adopt_workflow(workflow: WorkflowDefinition, decision: AdoptionDecision) -> None`
   - `AdoptionDecision` model with: `author`, `approved_by`, `rationale`, `source_work_ids`
3. **Implement**: An `InMemoryWorkflowAdoptionPort` or filesystem-based implementation where `adopt_workflow` validates and persists a `WorkflowDefinition` (potentially adding minimal provenance metadata to the YAML).
4. **Wire**: `build_workflow_lookup` would only discover workflows that have been "adopted" (e.g., via an `adopted: true` marker in the YAML, or a separate adopted-workflows index), NOT every YAML file on disk.
5. **Tests**: Prove that a non-adopted workflow (e.g., a draft YAML) is NOT returned as `EXISTING_WORKFLOW` by OCP.
6. **No synthesis**: This increment establishes the *decision boundary*, not the *decision automation*. The adoption decision itself remains human-mediated through the port.

This would close the central gap (T.1) while keeping all automation out of scope (per section O).
