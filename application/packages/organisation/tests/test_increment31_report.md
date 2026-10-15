# Increment 31 — Capability, Skill & Tool Boundary
## Final Report

---

## A. Architecture Discovered

### Current state of the five concepts:

| Concept | Location | Definition |
|---|---|---|
| **Capability** | `people_capability/src/capability.py` | An organisational ability/outcome contract. Answers WHAT. Has `CapabilityKind` (TOOL\|SKILL) and `CapabilityStatus` (DRAFT\|ACTIVE\|DEPRECATED). Does NOT enumerate supporting Skills. |
| **Skill** | `people_capability/src/skill.py` | A learned, reusable method for exercising a Capability. Answers HOW. Has `capability_id` (backward reference to its Capability) and `method` (human-readable description). |
| **Tool** | `people_capability/src/tool.py` | An executable resource available to Actor/Skill/Capability/Workflow. Answers WITH WHAT. Has `implementation_type` (abstract mechanism enum) and `implementation_ref` (string resolved by execution adapter). Has `supports` (reverse references to capabilities/skills it supports). |
| **Actor** | `people_capability/src/actor.py` | Unified organisational identity for Person/Agent. Answers WHO. `actor_type` discriminates PERSON\|AGENT. |
| **WorkflowDefinition** | `workflow_runner/models.py` | A reusable execution pattern with ordered `Step`s. Each `Step` has a `type` (WORKFLOW\|SKILL\|TOOL) and `uses` (string reference). Answers WHEN (reusable pattern). |

### Key architectural boundaries:
- **Capability lifecycle/discovery** → owned by `CapabilityRegistry` (established Increment 30)
- **Capability domain model** → owned by `people_capability`
- **Workflow execution mechanics** → `workflow_runner` package (executor, handlers, composer)
- **Execution binding** → `CapabilityDeployment` in `workflow_runner/src/` (Operations plane)
- **Capability execution contract** → `CapabilityExecutionPort` Protocol in `contracts/`

### What was found:
- **Capability → Skill**: `Skill.capability_id` already establishes the backward relationship (Skill references its Capability). But `Capability` does NOT have a `skill_ids` field — it does not enumerate supporting Skills.
- **Skill → Tool**: **No relationship existed.** `Tool.supports` referenced capability/skill IDs from the Tool side, but `Skill` had no `tool_ids` field.
- **Actor → Capability**: `CapabilityAssignment` is the authoritative mechanism, linking `actor_id` → `capability_id`.
- **skill_ids/tool_ids on CapabilityAssignment**: Added in Increment 28. Currently carry references — semantics are "authorised subset" (which skills/tools the actor may use for this capability).
- **Workflow runner models** (`SkillDefinition`, `ToolDefinition`): These are implementation specs (prompt templates, command templates) in `workflow_runner/models.py`. They are distinctly different from the domain `Skill` and `Tool` models but were not formally distinguished.
- **CapabilityExecutionPort**: Takes `capability_id`, `context`, `actor_context`. Does NOT conflate skill/tool/workflow — execution is resolved via `CapabilityDeployment` and `deployment_factory`.

---

## B. Capability Definition

**Location**: `packages/people_capability/src/capability.py:43`

A **Capability** is an organisational ability or outcome contract. It answers: *What can the organisation accomplish?*

Key fields:
- `id: str` — unique identifier
- `name: str` — human-readable name
- `capability_kind: CapabilityKind` — TOOL or SKILL (categorisation, not a reference)
- `status: CapabilityStatus` — DRAFT, ACTIVE, DEPRECATED
- `interface: CapabilityInterface` — inputs, outputs, errors
- `owns_durable_state: bool` — whether the capability manages persistent state
- `standing_contract: bool` — whether it has a standing operational contract
- `metadata`, `payload` — extensible fields

**Key design decision**: `Capability` does NOT enumerate its supporting Skills. A Capability may have zero or many Skills supporting it. Some capabilities may be directly executable without any Skills. The relationship flows from Skill → Capability (via `Skill.capability_id`), not from Capability → Skill.

---

## C. Skill Definition

**Location**: `packages/people_capability/src/skill.py:22`

A **Skill** is a learned, reusable method for exercising a Capability. It answers: *How can the capability be exercised?*

Key fields:
- `id: str` — unique identifier
- `capability_id: str` — the Capability this Skill supports (Capability → Skill relationship)
- `name: str`
- `description: str`
- `tags: list[str]`
- `method: str | None` — human-readable description of the learned technique
- **`tool_ids: list[str]`** — *(NEW in Increment 31)* Optional list of Tool IDs the Skill requires or can use
- `metadata`, `created_at`, `updated_at`

**Key design decisions**:
- A Skill is NOT a prompt, Python function, LangGraph node, or Paperclip skill. Those are concrete implementations.
- The `tool_ids` field establishes the Skill → Tool relationship — this was the primary addition in this increment.
- `tool_ids` defaults to empty — not every skill requires tools.

---

## D. Tool Definition

**Location**: `packages/people_capability/src/tool.py:38`

A **Tool** is an executable resource available to an Actor/Skill/Capability/Workflow. It answers: *With what executable resource?*

Key fields:
- `id: str`, `name: str`
- `implementation_type: ToolImplementationType` — PYTHON, MCP, HTTP_API, PAPERCLIP, LANGGRAPH, EXTERNAL_SERVICE
- `implementation_ref: str | None` — resolved by the execution adapter (module path, MCP name, agent ID, URL, etc.)
- `supports: list[str]` — IDs of Capabilities/Skills this Tool supports (reverse reference)
- `tags`, `metadata`, timestamps

**Key design decision**: `ToolImplementationType` describes the *mechanism*, not the implementation details. Adapters in the execution layer map these to concrete runtimes. The domain model never imports Paperclip, MCP, or LangGraph.

---

## E. WorkflowDefinition Distinction

**Location**: `packages/workflow_runner/models.py:33`

**WorkflowDefinition** is a reusable, understood execution pattern. It answers: *In what reusable execution pattern?*

A `WorkflowDefinition` has:
- `name`, `description`, `version`
- `steps: list[Step]` — ordered execution steps
- `Step` has `type` (StepType enum: WORKFLOW, SKILL, TOOL) and `uses` (string reference to skill/tool/sub-workflow name)

**Distinction from Skill**:
- A `WorkflowDefinition` is NOT a Skill. A Skill may eventually be incorporated into a WorkflowDefinition, but it does not become one.
- `WorkflowDefinition` has `steps`; `Skill` does not.
- `Skill` has `method` and `capability_id`; `WorkflowDefinition` does not.
- A `Step` references skills/tools by name (string `uses`), not by domain model objects.

**Distinction from workflow_runner's `SkillDefinition`/`ToolDefinition`**:
- `workflow_runner/models.py` defines `SkillDefinition` (a prompt template spec) and `ToolDefinition` (a command spec). These are implementation-level specs for the workflow runtime, NOT the domain `Skill`/`Tool` models from `people_capability`.
- The domain `Skill` has `capability_id` and `tool_ids`; `SkillDefinition` does not.
- The domain `Tool` has `implementation_type` and `implementation_ref`; `ToolDefinition` has `action` instead.

---

## F. Relationships Implemented

### 1. Capability → Skill (backward reference, already established, tests added)
- `Skill.capability_id` links a Skill to its supporting Capability
- A Capability does NOT enumerate supporting Skills (by design — skills are discoverable via the registry)
- **Status**: Relationship confirmed and tested

### 2. Skill → Tool (NEW — `tool_ids` field added)
- `Skill.tool_ids` establishes the forward relationship: which Tools a Skill requires or can use
- These are ID references only — actual Tool definitions remain in the people_capability domain
- Defaults to empty list — not every Skill requires Tools
- **Status**: Implemented and tested

### 3. Actor → Capability (already established)
- `CapabilityAssignment` is the authoritative mechanism
- `actor_id` → `capability_id`, with `skill_ids`/`tool_ids` as optional references
- **Status**: Confirmed and tested

### 4. Actor → Skill
- **Not established** — and intentionally so. Skills are available through assigned Capabilities, not via a separate Actor → Skill assignment. This was a deliberate decision per the increment requirements.
- **Status**: Documented and tested as intentional non-implementation

### 5. Tool → Skill/Capability (reverse reference, already established)
- `Tool.supports` references capability/skill IDs the Tool supports
- **Status**: Confirmed

---

## G. CapabilityAssignment Decision

**Decision**: CapabilityAssignment remains the authoritative mechanism for Actor ↔ Capability.

**skill_ids / tool_ids on CapabilityAssignment** — kept as-is. Decision: **retain, document, and test semantics**.

These fields represent an **authorised subset / available implementation** mechanism:
- They are **references only** (lists of string IDs), not model objects
- They are **optional** (default to empty)
- They allow the organisation to specify which Skills and Tools an Actor may use while exercising a specific Capability
- They are **not** a separate Actor → Skill assignment mechanism — the primary link is `capability_id`

**No destructive removal** was performed. The fields have legitimate semantics (authorised subset of implementation resources) and existing tests (`test_actor.py:267`, `test_actor.py:278`) depend on them.

---

## H. skill_ids / tool_ids Decision

**Decision**: `skill_ids` and `tool_ids` on `CapabilityAssignment` are retained.

**Rationale**: They serve as an **authorised subset / available implementation** filter. When an Actor is assigned a Capability, the organisation may restrict which specific Skills and Tools the Actor can use within that Capability. This is an organisational governance concern, not an implementation concern.

**On `Skill.tool_ids`**: This new field establishes the **forward** Skill → Tool relationship. The `Tool.supports` field provides the **reverse** Tool → Skill/Capability relationship. Together they form a bidirectional link:
- `Skill.tool_ids` → "which Tools does this Skill use?"
- `Tool.supports` → "which Capabilities/Skills can this Tool support?"

Both are ID references. Neither embeds implementation objects.

---

## I. CapabilityExecutionPort Impact

**Location**: `packages/contracts/capability_execution.py:11`

`CapabilityExecutionPort` is a Protocol with a single method:
```python
def execute(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any]) -> ExecutionResult
```

**No conflation detected**: The port takes `capability_id` only — it does NOT take `skill_id`, `tool_id`, or `workflow_id` parameters. The execution contract remains organisationally meaningful without becoming tied to:
- Paperclip
- LangGraph
- Worker internals
- MCP

**No changes required**. The port is already cleanly separated from implementation details. Execution resolution happens downstream in `CapabilityExecutionAdapter` which consults the deployment factory and authorisation port.

---

## J. Registry Impact

**No new registries created.**

- `CapabilityRegistry` (in `capability_registry/src/capabilities.py`) remains the sole lifecycle authority for Capabilities
- `Skill` and `Tool` are subordinate domain concepts referenced by ID from `CapabilityAssignment` and `Skill` itself
- No `SkillRegistry` or `ToolRegistry` was created — Skills and Tools are domain models that exist as references within other entities (CapabilityAssignment, Skill)
- The `workflow_runner/registry.py` `Registry` class is a filesystem-backed catalog for the execution layer (prompts, commands, workflows) — it is implementation, not organisational domain

**No changes required**.

---

## K. Learning-Loop Impact

The learning loop is **unchanged**:

```
Capability gap
      ↓
    Work
      ↓
DRAFT Capability
      ↓
  Assessment
      ↓
ACTIVE Capability
      ↓
CapabilityAssignment    ← (Actor → Capability)
      ↓
      Actor
```

**Where Skills fit conceptually**:

```
Capability gap
      ↓
    Work
      ↓
learned capability
      ↓
useful method
      ↓
      Skill            ← (Skill → Capability via capability_id, Skill → Tool via tool_ids)
      ↓
reusable capability exercise
      ↓
WorkflowDefinition     ← (may incorporate Skills, is not itself a Skill)
```

This relationship is now **structurally supported** by the domain model:
- `Skill.capability_id` links a learned method to its Capability
- `Skill.tool_ids` links a method to the Tools it uses
- No automatic skill extraction was implemented — this is conceptual only

---

## L. Paperclip / LangGraph Impact

**No changes to Paperclip or LangGraph.**

- `PaperclipOrganisationControlPlane` remains behind the `OrganisationControlPlane` abstraction
- It delegates capability registration to `CapabilityRegistry` (not the domain Skill/Tool models)
- The `ToolImplementationType.PAPERCLIP` and `ToolImplementationType.LANGGRAPH` enum values are **abstract mechanism identifiers** — they are never imported from or coupled to concrete implementations
- Paperclip adapter does not define domain concepts (`Skill`, `Tool`, `CapabilityAssignment`, etc.) — verified by AST inspection in existing Increment 28 tests

---

## M. Tests and Results

**27 new architectural tests** added in `packages/organisation/tests/test_increment31_capability_skill_tool_boundary.py`:

### Capability distinction
- `test_capability_is_distinct_from_skill` — Capability and Skill are different classes with different fields
- `test_capability_kind_enum_not_skill_enum` — CapabilityKind is an enum, not a Skill reference

### Skill distinction
- `test_skill_is_distinct_from_tool` — Skill and Tool are different classes with different fields
- `test_skill_has_tool_ids_field` — Skill has the new `tool_ids` field
- `test_workflow_definition_is_distinct_from_skill` — WorkflowDefinition ≠ Skill (different fields)
- `test_workflow_step_type_enums_skill_and_tool_as_invocation_targets` — StepType is an Enum, not a Skill class
- `test_workflow_runner_models_skill_definition_is_not_domain_skill` — workflow_runner's SkillDefinition ≠ domain Skill
- `test_workflow_runner_models_tool_definition_is_not_domain_tool` — workflow_runner's ToolDefinition ≠ domain Tool

### Tool distinction
- `test_tool_does_not_couple_to_paperclip_models` — Tool's implementation_ref is a string, not a Paperclip object
- `test_tool_implementation_type_does_not_embed_paperclip_logic` — ToolImplementationType lists mechanisms

### Capability → Skill relationship
- `test_skill_references_capability_via_capability_id` — Skill.capability_id links to its Capability
- `test_capability_does_not_require_skills` — Capability has no skill_ids (doesn't enumerate skills)

### Skill → Tool relationship
- `test_skill_can_reference_tools_via_tool_ids` — Skill.tool_ids references Tool IDs
- `test_skill_tool_ids_defaults_empty` — tool_ids defaults to empty list

### Actor → Capability
- `test_actor_to_capability_via_assignment` — CapabilityAssignment links Actor to Capability
- `test_no_actor_to_skill_direct_assignment_required` — No separate Actor→Skill assignment

### skill_ids/tool_ids semantics
- `test_capability_assignment_skill_ids_are_references` — skill_ids/tool_ids are string references
- `test_capability_assignment_skill_ids_optional` — Default to empty

### No backend leakage (AST inspection of people_capability source)
- `test_people_capability_does_not_import_paperclip`
- `test_people_capability_does_not_import_langgraph`
- `test_people_capability_does_not_import_workflow_runner`
- `test_people_capability_does_not_import_mcp`
- `test_people_capability_does_not_import_organisation`

### CapabilityExecutionPort
- `test_capability_execution_port_takes_capability_id_only` — No skill_id/tool_id/workflow_id params
- `test_capability_execution_port_is_protocol_no_concrete_impl` — It's a Protocol

### Workflow distinction
- `test_workflow_definition_step_uses_references_not_models` — Steps reference by string
- `test_skill_is_not_workflow_definition` — Skill lacks `steps`, WorkflowDefinition lacks `method`

### Test results:
- **27 passed, 0 failed**
- **790 passed** total (up from 763 in Increment 30)
- **60 pre-existing failures** (unchanged — all in `test_capability_execute.py` and `test_platform_integration.py`)
- **4 skipped, 13 deselected** (unchanged)
- **Ruff: clean** for all Increment 31 files

---

## N. Pre-existing Failures

60 failures remain in:
- `packages/workflow_runner/tests/test_capability_execute.py` — tests requiring live API/database infrastructure
- `packages/workflow_runner/tests/test_platform_integration.py` — tests requiring live AI/runtime infrastructure

These are the same 60 failures documented in Increment 30's baseline. No new failures were introduced. No changes were made to `workflow_runner` or its test suite.

---

## O. Remaining Architectural Gaps

1. **Skill lifecycle**: Skills are created as domain models but have no registry or lifecycle management. There is no `SkillRegistry` — Skills are currently only referenced by ID from `CapabilityAssignment` and `Skill.capability_id`. When a Skill needs to be persisted and retrieved, a Skill repository/registry will be needed.

2. **Tool lifecycle**: Tools face the same gap — no ToolRegistry. Tools are referenced by `Tool.supports` and `Skill.tool_ids` but have no persistence layer.

3. **Skill→Tool resolution at execution time**: The `tool_ids` on Skill and `supports` on Tool are ID references. There is no execution-time mechanism that resolves a Skill's `tool_ids` into actual executable Tool implementations. This would require a Tool resolution adapter in the execution layer.

4. **WorkflowDefinition ↔ domain model mapping**: The workflow_runner's `Step` model references skills/tools by name (string `uses`), but there is no formal link between these names and the domain `Skill`/`Tool` IDs. A mapping/adaptation layer would be needed to connect WorkflowDefinition steps to domain Skill/Tool references.

5. **WorkflowDefinition is not yet persisted**: WorkflowDefinitions live in the workflow_runner package and are loaded from YAML files. There is no organisational registry for workflows — only the execution-layer `Registry` in `workflow_runner/registry.py`.

---

## P. Recommended Increment 32

**Increment 32: Skill & Tool Persistence via CapabilityRegistry**

**Objective**: Establish persistence and retrieval for Skills and Tools without creating separate registries.

**Proposed approach**:
1. Extend `CapabilityRegistry` (or its repository) to also store and retrieve `Skill` and `Tool` domain models — they are subordinate concepts that can live alongside Capabilities without their own lifecycle authority.
2. Add `register_skill(skill)`, `get_skill(skill_id)`, `list_skills()` to CapabilityRegistry.
3. Add `register_tool(tool)`, `get_tool(tool_id)`, `list_tools()` to CapabilityRegistry.
4. Ensure the `Tool.supports` and `Skill.tool_ids` cross-references are validated on registration.
5. Add adapter in the execution layer that resolves a Skill's `tool_ids` into `Capability` or `ToolDefinition` references for workflow execution.

**Tests**:
- Register and retrieve a Skill through the registry
- Register and retrieve a Tool through the registry
- Verify `Skill.tool_ids` and `Tool.supports` cross-references are consistent
- Verify no separate SkillRegistry/ToolRegistry is needed
- Prove domain Skill/Tool models remain free of Paperclip/LangGraph/workflow_runner imports

**Do NOT**:
- Create separate SkillRegistry or ToolRegistry classes
- Add automatic skill extraction from work
- Build a skill marketplace or knowledge graph
- Make Tool a Paperclip/MCP-specific concept
