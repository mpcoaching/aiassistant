# Increment 8 — Organisational Workflow Validation: Investigation Report

## Executive Summary

The four-plane architecture (Enterprise, Organisation/Control, People/Capability, Operations) is **coherent and valid**. The domain model can represent a real organisation without requiring CEO → everything, OrganisationControlPlane → everything, People/Capability → everything, or Operations → everything.

However, the **current code does not yet implement the validated model**. Several contradictions exist between the architectural decisions (ADRs 026–036) and the current domain records in `packages/organisation/src/role.py`. These must be resolved before Increment 8 implementation.

**No production code was changed during this investigation.**

---

## 1. Validated Architecture

The two-dimensional model is valid:

- **Dimension A (Organisational Work):** Strategic intent → strategic decision → accountability → coordination → Work → operational execution → outcome → review/learning
- **Dimension B (Capability):** Role requires Capability → People/Capability ensures readiness → Person/Agent fulfils Role

These dimensions intersect but do NOT collapse. A Work item may require capabilities, but Work is not a capability. A Role may require capabilities, but a Role is not a capability. A Person/Agent may possess capabilities, but the Person/Agent is not the capability.

---

## 2. Work Domain Model

### What is Work?

Work is a **concrete body of effort required to produce an outcome**, accountable to a Role. It is an organisational assignment, not an execution unit. Operations creates execution units (sessions, workflows) from Work.

### Minimum Work Model

| Field | Type | Purpose |
|---|---|---|
| `id` | str | Unique identifier |
| `title` | str | Descriptive title |
| `description` | str | Detailed description |
| `work_type` | str | "bau" \| "project" \| "initiative" |
| `status` | WorkStatus | pending \| assigned \| in_progress \| completed \| cancelled \| escalated |
| `priority` | str | normal \| high \| critical |
| `accountable_role_id` | str | **REQUIRED.** Role accountable for outcome |
| `coordinating_role_id` | str \| None | Role coordinating the work |
| `requested_by_role_id` | str \| None | Role that requested the work |
| `assignee_role_id` | str \| None | Role assigned to perform work |
| `assignee_person_id` | str \| None | Specific person assigned |
| `assignee_agent_id` | str \| None | Specific agent assigned |
| `required_capability_ids` | list[str] | Capabilities required by this work |
| `acceptance_criteria` | list[str] | Outcome criteria for completion |
| `dependencies` | list[str] | Work IDs this work depends on |
| `parent_work_id` | str \| None | Parent work for decomposition |
| `deliverables` | list[str] | Expected deliverables |
| `outcome` | dict \| None | Actual outcome when completed |
| `constraints` | list[str] | Constraints |
| `context` | dict[str, Any] | Additional context |
| `created_at`, `updated_at` | datetime | Timestamps |
| `metadata` | dict[str, Any] | Additional metadata |

### Key Answers

1. **Is Work an organisational assignment, a desired outcome, or an execution unit?**
   Work is an organisational assignment that produces an outcome. Operations creates execution units from Work.

2. **Should Work have both accountable_role and coordinating_role?**
   Yes. They can be the same (simple BAU work) or different (project work).

3. **Can accountable_role_id and coordinating_role_id be the same?**
   Yes, for simple work where the accountable role also coordinates.

4. **Can they be different?**
   Yes, for project work where a C-Suite executive is accountable and a PM coordinates.

5. **Can a Work item have multiple people/agents assigned?**
   Yes, through multiple Assignment records. The current Assignment model supports this.

6. **Can specialist sub-work exist?**
   Yes, through `parent_work_id` and `dependencies`.

7. **Does Work need parent/child relationship?**
   Yes, for decomposing large projects into smaller work items.

8. **Does Work need dependencies?**
   Yes, for sequencing and coordination between work items.

9. **Does Work need milestones?**
   Milestones are a project management view of Work, not a domain model concern. They can be represented as Work with specific types or as metadata.

10. **Does Work need status?**
    Yes, already has WorkStatus.

11. **Which are organisational vs PM concerns?**
    - Organisational: `accountable_role_id`, `coordinating_role_id`, `work_type`, `requested_by_role_id`
    - PM concerns: `dependencies`, `parent_work_id`, `priority`
    - Both: `status`, `acceptance_criteria`, `outcome`

---

## 3. BAU Model — Validated

### Scenario: KPI Deterioration

1. **Operations detects deterioration** — operational monitoring (transient state)
2. **Functional manager observes** — Role observes operational performance
3. **Functional manager creates Work** — `work_type="bau"`, `accountable_role_id=functional_manager_id`, `coordinating_role_id=functional_manager_id`
4. **Work assigned to operational role** — Assignment record created
5. **Operations executes** — Operations plane executes the work
6. **Outcome recorded** — `Work.outcome` populated
7. **Functional manager reports to COO** — information flows upward
8. **COO observes** — COO Role observes organisational performance
9. **CEO intervenes only if threshold exceeded** — strategic intervention

**Accountability test:**
1. Who is accountable? → Functional manager (`accountable_role_id`)
2. Who has authority? → Functional manager's Authority records
3. Who coordinates? → Functional manager (`coordinating_role_id`)
4. Who performs the work? → Assigned operational role
5. Who ensures capability exists? → People/Capability plane

**No CEO → task → agent required. No OrganisationControlPlane → everything required. No People/Capability → everything required. No Operations → everything required.**

---

## 4. Strategic Project Model — Validated

### Scenario: Enter New Market

1. **CEO makes strategic decision** — "We should enter market X."
2. **C-Suite executive becomes accountable** — e.g., CMO accountable for business outcome
3. **PM assigned to coordinate** — PM coordinates delivery
4. **PM creates initiative Work** — `work_type="project"`, `accountable_role_id=CMO_id`, `coordinating_role_id=PM_id`
5. **PM decomposes into specialist Work items** — EA, BA, SA, Designer, Developer, QA each get Work
6. **Specialist roles perform work** — each produces work products
7. **Operations executes where needed** — runtime execution of workflows
8. **Outcomes flow upward** — Work.outcome populated, reported to CMO
9. **CMO evaluates business outcome** — accountable executive evaluates
10. **CEO observes** — CEO reviews outcome, may make further strategic decision

**Accountability test:**
1. Who is accountable? → C-Suite executive (`accountable_role_id` on initiative Work)
2. Who has authority? → C-Suite executive's Authority + PM's coordination authority
3. Who coordinates? → Project Manager (`coordinating_role_id`)
4. Who performs the work? → Specialist roles (EA, BA, SA, Dev, QA)
5. Who ensures capability exists? → People/Capability plane

**No CEO orchestrator required. No OrganisationControlPlane brain required.**

---

## 5. Specialist Role Handoffs — Validated

### Mechanism

Work handoffs between roles are represented through:
1. **Work decomposition** — parent Work split into child Work items
2. **Assignment records** — each Work assigned to specific Role/Person/Agent
3. **Dependencies** — Work A depends on Work B completion
4. **Status transitions** — Work.status moves through lifecycle

The flow:

```
Accountable Executive
    ↓
Project Manager (coordinates initiative Work)
    ↓
EA Work (design) → BA Work (analysis) → SA Work (architecture)
    ↓
Designer Work → Developer Work → QA Work
    ↓
Operations (execution where required)
```

Each Work item has:
- `accountable_role_id` (who owns the outcome)
- `coordinating_role_id` (who coordinates delivery)
- `assignee_role_id` (who performs the work)
- `required_capability_ids` (what capabilities are needed)
- `dependencies` (what must complete first)

**No workflow engine is required at the domain level.** Workflow execution remains in Operations. The domain model represents *what* needs to happen; Operations represents *how* it happens.

---

## 6. Role / Person / Agent / Capability Model — Validated with Correction Needed

### Validated Model

```
Person / Agent
      |
      | fulfils
      v
    Role
      |
      | requires
      v
  Capability
      ^
      | possesses / fulfils
Person / Agent
```

### Critical Contradiction Discovered

**Current code:** `Person` and `Agent` are defined in `packages/organisation/src/role.py` (Organisation/Control plane).

**Architecture (ADR-026):** Person records belong to People/Capability plane.

**Resolution:** Person and Agent domain records must move to People/Capability plane. Organisation/Control references them by ID only.

However, this creates a coupling challenge: OrganisationControlPlane needs to assign Work to Person/Agent. Options:

1. **Person/Agent in People/Capability, Organisation/Control references by ID** — Clean boundary, but Organisation/Control imports from People/Capability (violates import-clean if not careful).
2. **Shared kernel** — Person/Agent in a shared kernel package. Both planes import from it.
3. **Organisation/Control defines lightweight references** — Organisation/Control uses `person_id` and `agent_id` strings; People/Capability owns the full records.

**Recommended: Option 3.** Organisation/Control uses IDs. People/Capability owns full Person/Agent records and capability readiness. This preserves the import-clean principle and the plane boundaries.

### Capability Assignment

- **"Requires capability"** is a Role concern (Role.required_capability_ids)
- **"Possesses capability"** is a People/Capability concern (Person.capability_ids, Agent.capability_ids)
- **"Required capability for this Work"** is a Work concern (Work.required_capability_ids)

The system CAN determine whether an assignee is capable of performing assigned Work WITHOUT making OrganisationControlPlane responsible for capability matching. People/Capability provides the capability readiness check; OrganisationControlPlane uses the result.

---

## 7. People / Capability Boundary — Validated

### Lifecycle

```
capability gap identified
    ↓
capability specified
    ↓
develop / acquire
    ↓
test
    ↓
register
    ↓
make available to roles / people / agents
    ↓
operate
    ↓
measure
    ↓
learn
    ↓
retire
```

### Who Identifies Gaps?

Anyone may OBSERVE a gap:
- CEO: "We strategically need capability X."
- COO: "Our operations lack capability X."
- C-Suite executive: "This initiative requires capability X."
- PM: "This project cannot proceed without capability X."
- Functional manager: "My team lacks capability X."
- Role: "This role requires capability X."
- People/Capability: "Capability X is missing from the registry."

But People/Capability OWNS the capability lifecycle. The PM does not become the capability owner. The CEO does not become the capability owner.

### Validation

```
PM: "This project cannot proceed because we lack capability X."
    ↓
People/Capability: "Capability X does not currently exist."
    ↓
People/Capability: "We will develop/acquire it."
    ↓
People/Capability: registers Capability X
    ↓
Capability X available to roles
    ↓
Work can now be performed
```

This distinction holds.

---

## 8. Capability / Skill / Tool — Under Investigation

The current model treats Skills and Tools as Capability kinds (`CapabilityKind.SKILL`, `CapabilityKind.TOOL`). This served well for early exploration but may obscure distinctions.

**Proposed conceptual model:**

```
Capability
   ├── knowledge
   ├── skills
   ├── methods
   ├── tools
   └── resources
```

Where:
- **Capability** = ability to reliably produce an outcome
- **Skill** = component of that ability (knowledge, method, technique)
- **Tool** = something used to enable/support that ability
- **Resource** = supporting material or infrastructure

**Recommendation:** Keep the current unified `Capability` type for now. The distinction can be expressed through `Capability` metadata, tags, and relationships rather than through separate domain types. Splitting into separate types adds complexity without clear benefit at this stage. Revisit when capability matching and acquisition require the distinction.

---

## 9. OrganisationControlPlane Boundary — Correction Needed

### Current Problem

`OrganisationControlPlane` currently:
- Stores roles, persons, agents, authorities, work, assignments, delegations
- Provides role lookup, work assignment, authority delegation, organisational context

This makes it a **storage + mechanism hybrid**, which is a God service risk.

### Corrected Boundary

`OrganisationControlPlane` should provide **mechanisms and context only**:

- `get_role(role_id)` — retrieve role definition
- `list_roles()` — list active roles
- `get_organisational_context(request)` — derive context from request
- `create_assignment(work, assignee)` — create assignment record (mechanism)
- `get_work(work_id)` — retrieve work
- `delegate_authority(from_role, to_role, authority)` — create delegation record (mechanism)
- `record_work_outcome(work_id, outcome)` — record outcome (mechanism)

It should NOT:
- Store Person/Agent records (owned by People/Capability)
- Coordinate work (belongs to roles)
- Become the CEO/COO/PM
- Execute work

### Paperclip Test

If Paperclip replaced OrganisationControlPlane, would the domain model still make sense?

**Currently: No.** Because OCP conflates domain types with storage mechanisms. Person and Agent are defined in the organisation package, making them part of the Organisation/Control domain model.

**After correction: Yes.** The domain model (Role, Work, Authority, Assignment) is independent of the storage mechanism. Paperclip can implement role storage, work assignment, and coordination behind the OrganisationControlPlane abstraction.

---

## 10. Paperclip Mapping — Validated

| Our Concept | Paperclip Concept | Mapping Quality |
|---|---|---|
| Role | Agent / Team | Clean |
| Work | Task / work mechanism | Clean |
| Authority | Permissions / approvals | Clean |
| Assignment | Task assignment | Clean |
| Delegation | Delegation / chain | Clean |
| Reporting relationships | Hierarchy | Clean |
| Coordination | Meetings / coordination | Partial |
| Required capabilities | Not modelled | Missing |
| Accountability model | Not modelled | Missing |
| Enterprise assets | Not modelled | Missing |
| Governance | Not modelled | Missing |
| EIMS | Not modelled | Missing |

**Conclusion:** Paperclip fits naturally behind OrganisationControlPlane for organisational mechanisms. What Paperclip does NOT provide (capabilities, EIMS, governance, enterprise assets, accountability semantics) must remain ours.

---

## 11. EIMS Learning Loop — Validated

### What becomes durable EIMS knowledge

- Strategic decisions and rationale
- Capability definitions and maturation history
- Work outcomes (success, failure, lessons learned)
- Enterprise assets produced by roles
- Governance decisions (approved CapabilityRequests)
- Institutional learning (patterns, playbooks, policies)

### What remains transient

- Session state (running context, step outputs, human responses)
- Workflow execution state (current step, intermediate results)
- Runtime agent state (in-flight tool calls, temporary buffers)
- Human-in-the-loop pending state
- Operations monitoring state (KPIs, alerts)

### Validation

The learning loop is coherent:
1. Work → execution → outcome (Operations)
2. Outcome → assessment (operational concern)
3. Assessment → EnterpriseConcept (EIMS)
4. EnterpriseConcept → future decisions (Enterprise)

No plane becomes a God service. EIMS does not become a runtime database. Operations does not become the organisation's brain.

---

## 12. Mixed Human / AI Organisation — Validated

### Scenarios

| Scenario | CEO | PM | EA | Dev | QA | Ops |
|---|---|---|---|---|---|---|
| A: All human | Human | Human | Human | Human | Human | Human |
| B: AI-led | AI | Human | AI | AI | AI | AI |
| C: Mixed team | Human | AI | Human | Human+AI | Human+AI | AI |
| D: AI-heavy | AI | AI | AI | Human | AI | AI |

**The domain model does not change.** Only the entity fulfilling the Role changes.

This proves:
- **Role ≠ Person** (Role is abstract; Person is human)
- **Role ≠ Agent** (Role is abstract; Agent is software)
- **Role ≠ Capability** (Role has requirements; Capability is ability)

---

## 13. Accountability Test — All Scenarios Pass

### BAU Scenario
1. Accountable: Functional manager
2. Authority: Functional manager's Authority records
3. Coordinates: Functional manager
4. Performs: Assigned operational role
5. Capability: People/Capability plane

### Strategic Project Scenario
1. Accountable: C-Suite executive
2. Authority: C-Suite executive's Authority + PM coordination authority
3. Coordinates: Project Manager
4. Performs: Specialist roles (EA, BA, SA, Dev, QA)
5. Capability: People/Capability plane

### No scenario collapses to:
- "CEO" as universal answer
- "OrganisationControlPlane" as universal answer
- "People/Capability" as universal answer
- "Operations" as universal answer

---

## 14. Contradictions Discovered

| # | Contradiction | Location | Resolution |
|---|---|---|---|
| 1 | Person/Agent in Organisation/Control package but ADR-026 says People/Capability owns them | `packages/organisation/src/role.py` vs ADR-026 | Move Person/Agent to People/Capability; Organisation/Control references by ID |
| 2 | Work model lacks accountability/coordination fields | `packages/organisation/src/role.py` vs ADR-034 | Add fields to Work (not in this increment) |
| 3 | Role model lacks required_capability_ids and accountabilities | `packages/organisation/src/role.py` vs ADR-027, ADR-034 | Add fields to Role (not in this increment) |
| 4 | OrganisationControlPlane stores Person/Agent records | `organisation_control_plane.py` vs ADR-022 | OCP should not store Person/Agent; People/Capability owns them |
| 5 | OrganisationControlPlane is a storage + mechanism hybrid | `organisation_control_plane.py` vs ADR-022, ADR-036 | Separate mechanism from storage; storage is backend concern |

---

## 15. ADR Changes Required

### New ADRs

1. **ADR-037: Person/Agent Ownership by People/Capability** — Person and Agent domain records belong to People/Capability plane. Organisation/Control references them by ID. OrganisationControlPlane does not store Person/Agent records.

2. **ADR-038: Work Decomposition and Dependency Model** — Work supports parent/child decomposition and dependency tracking for project coordination.

### ADR Updates

1. **ADR-022:** Update to reflect OrganisationControlPlane as mechanism-only, not storage.
2. **ADR-027:** Update to clarify that Role has `required_capability_ids` and Person/Agent has `capability_ids`.
3. **ADR-034:** Update to reflect that `accountable_role_id` and `coordinating_role_id` are required on Work.
4. **ADR-036:** Update to reflect that coordination is role-level, not plane-level.

---

## 16. Architecture Documentation Changes Required

1. Update `.kilo/context/architecture.md`:
   - Add validated Work domain model
   - Add BAU and project scenario walkthroughs
   - Add Person/Agent ownership clarification
   - Add OrganisationControlPlane mechanism-only boundary
   - Add Paperclip mapping table
   - Add accountability test results
   - Update Increment 8 scope

2. Create Increment 8 investigation report (this document).

---

## 17. Revised Increment 8 Proposal

### In Scope (Smallest Increment to Prove Architecture)

1. **Correct Person/Agent ownership:**
   - Document that Person/Agent records belong to People/Capability plane
   - Organisation/Control references Person/Agent by ID
   - Update ADR-037

2. **Extend Work model with minimum accountability fields:**
   - `work_type`: "bau" | "project" | "initiative"
   - `accountable_role_id`: str (REQUIRED)
   - `coordinating_role_id`: str | None
   - `outcome`: dict | None
   - `acceptance_criteria`: list[str]
   - `required_capability_ids`: list[str]
   - `dependencies`: list[str]
   - `parent_work_id`: str | None
   - Update tests to verify Work accountability model

3. **Extend Role model with required capabilities:**
   - `required_capability_ids`: list[str]
   - Update tests

4. **Add architectural boundary tests:**
   - Verify Work does not import capability definitions
   - Verify Person/Agent are not in organisation package (or are reference-only)
   - Verify OrganisationControlPlane does not store Person/Agent records

5. **Document Paperclip mapping:**
   - Create conceptual mapping table in architecture.md

### Out of Scope

- Full People/Capability service implementation
- Full CEO implementation as strategic role
- COO implementation
- C-Suite executive roles
- Project Manager implementation
- Paperclip integration
- EIMS expansion beyond ConceptStore
- EnterpriseInformation abstraction implementation
- All specialist role implementations
- Assistant redesign
- Capability matching implementation
- Capability execution in CEO
- Universal routing
- Capability/Skill/Tool split (ADR-035 remains proposed)

---

## 18. Explicit List of Things NOT to Implement Yet

1. People/Capability plane package and services
2. CEO as strategic role implementation
3. COO implementation
4. C-Suite executive roles
5. Project Manager implementation
6. Specialist role implementations (EA, SA, BA, Developer, QA)
7. Paperclip adapter
8. EIMS expansion beyond ConceptStore
9. EnterpriseInformation abstraction
10. Capability routing in AssistantChatService
11. Capability matching implementation
12. Capability execution in CEO
13. Universal routing
14. Capability/Skill/Tool type split
15. OutcomeRecorder / LearningService
16. Assistant redesign

---

## 19. Success Criterion — Met

The architecture demonstrates:

```
Enterprise
   ↓
strategic direction
   ↓
CEO (strategic decision)
   ↓
appropriate accountable executive
   ↓
management / project coordination
   ↓
organisational roles
   ↓
Operations
   ↓
outcomes
   ↓
enterprise learning
```

while independently:

```
Role
   ↓ requires
Capability
   ↓
People/Capability ensures readiness
   ↓
Person / Agent fulfils Role
```

And:

```
OrganisationControlPlane
    provides organisational mechanisms/context
    but does NOT become the organisation's brain.
```

The key tests pass:
- CEO makes strategic decisions without becoming work orchestrator ✓
- COO manages BAU without becoming Operations engine ✓
- C-Suite executive owns initiative without becoming PM ✓
- PM coordinates delivery without becoming execution engine ✓
- People/Capability ensures capability readiness without becoming work manager ✓
- Roles carry responsibility and accountability without being confused with People, Agents, or Capabilities ✓
- Organisation operates with humans, AI agents, or mixed teams without changing domain model ✓
