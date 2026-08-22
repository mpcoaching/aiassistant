# Increment 13 — People / Capability Plane: Architectural Investigation Report

## Executive Summary

The People/Capability plane is the next major unresolved domain boundary. This investigation
determines what it actually owns, how it relates to the other three planes, and what the
smallest defensible Increment 14 should be.

**Key finding:** The People/Capability plane is not a "capability service" that everything calls.
It is a domain plane owning the workforce (Person/Agent records) and reusable abilities
(Capability definitions, lifecycle, assignment, proficiency). It provides candidates and
availability information; it does not select, authorise, or execute on behalf of other planes.

---

## 1. What exactly does the People/Capability plane own?

The People/Capability plane owns:

1. **Person records** — human individuals with identity and employment context
2. **Agent records** — software entities with marker, runtime identity, and fulfilled roles
3. **Capability definitions** — reusable abilities (tools, skills, services) with interface
4. **Capability lifecycle** — identify → specify → develop/acquire → test → register →
   assign → operate → measure → learn → retire
5. **CapabilityAssignment** — the record that a specific Person/Agent is assigned/authorised
   to use a specific Capability
6. **CapabilityProficiency** — how well a Person/Agent can exercise a Capability
7. **Capability matching** — determining who has what capability, who needs what
8. **CapabilityRequest governance** — requesting NEW capabilities (transient governance object)
9. **Capability gap analysis** — determining what capabilities are needed but unavailable

It does NOT own:
- Work
- Work assignment
- Operational execution
- EIMS
- Capability execution
- Capability discovery by Operations
- Organisational coordination

---

## 2. Correct relationships between domain concepts

```
Person / Agent (People/Capability plane)
    |   possesses / assigned
    |   (CapabilityAssignment + CapabilityProficiency)
    v
Capability (People/Capability plane)
    ^
    | requires
Role (Organisation/Control plane)
    |
    | occupied by / fulfilled by
    v
Person / Agent (People/Capability plane)

Work (Organisation/Control plane)
    | required_capability_ids
    v
Capability (People/Capability plane)

Work (Organisation/Control plane)
    | assigned to
    v
Role / Person / Agent (Organisation/Control plane — by ID only)
```

Key distinctions:
- **Role requires Capability**: Role declares what capabilities are needed for the position
- **Person possesses Capability**: Person has CapabilityAssignment + CapabilityProficiency records
- **Agent possesses/uses Capability**: Agent has CapabilityAssignment + CapabilityProficiency records
- **Work requires Capability**: Work declares what capabilities are needed for the effort
- **Possession ≠ Requirement**: A Role may require a capability that no current Person/Agent possesses. That is a gap.

---

## 3. Where should Person and Agent actually live?

**ADR-037 already decided this:** Person and Agent belong to People/Capability. Organisation/Control
references them by ID only.

**Current contradiction:** `packages/organisation/src/role.py` defines `Person` and `Agent` classes.
This violates ADR-037.

**Resolution:** Person and Agent must move to a new `packages/people_capability/src/` package.
Organisation/Control must continue to reference them by ID only (Work.assignee_person_id,
Work.assignee_agent_id, Role.fulfilled_role_ids references). The `role.py` module in
organisation must import Person/Agent from the people_capability package (or use string IDs
only in production code).

---

## 4. What it means for entities to require/possess capabilities

### Role requires Capability
- Role declares `required_capability_ids: list[str]`
- This is a **position requirement**, not an assignment
- It says "anyone fulfilling this Role should have these capabilities"
- It does NOT say "this specific Person has these capabilities"
- It does NOT create a CapabilityAssignment

### Person has a Capability
- Person has a **CapabilityAssignment** record linking them to the Capability
- CapabilityAssignment carries:
  - `person_id` or `agent_id`
  - `capability_id`
  - `assignment_type` (primary, secondary, backup)
  - `status` (active, suspended, expired)
  - `assigned_at`, `expires_at`
  - `authorised_by` (role or person who authorised)
- Person may also have a **CapabilityProficiency** record:
  - `person_id` or `agent_id`
  - `capability_id`
  - `proficiency_level` (novice, competent, proficient, expert, master)
  - `validated_at`, `valid_until`
  - `evidence` (certifications, test results, observed performance)

### Agent has a Capability
- Same model as Person: CapabilityAssignment + CapabilityProficiency
- Agent records additionally carry `runtime_identity` for runtime binding

### Work requires Capability
- Work declares `required_capability_ids: list[str]`
- This is a **work requirement**, not an assignment
- At Work creation/assignment time, People/Capability can assess whether required
  capabilities are available among assigned Person/Agent(s)
- If not, People/Capability identifies the gap and determines response

---

## 5. Can capabilities be transferred between roles/persons/agents?

**Yes, and the model must support this explicitly.**

A capability is a portable organisational asset. When a capability is transferred:

1. **People/Capability creates a new CapabilityAssignment** for the new holder
2. **People/Capability retires the old CapabilityAssignment** (status = expired/revoked)
3. **History is preserved** — CapabilityAssignment records are never deleted
4. **CapabilityProficiency is re-evaluated** for the new holder
5. **Organisation/Control is informed** that capability availability has changed
6. **Operations is informed** of who is now authorised to use the capability

This is NOT a Work assignment change. Capability transfer is a People/Capability concern.

---

## 6. Who is responsible for each lifecycle phase?

| Phase | Owner | Notes |
|---|---|---|
| Identify | People/Capability | Identifies capability gaps from Work requirements, strategic decisions |
| Specify | People/Capability + human approval | ADR-015: human approves specification |
| Develop/acquire | People/Capability | Decides build vs. acquire, manages development/training |
| Test/qualify | People/Capability | Tests capability, validates proficiency |
| Register | People/Capability | Registers in CapabilityRegistry (currently in capability_registry package) |
| Assign | People/Capability | Creates CapabilityAssignment for Person/Agent |
| Operate | Operations | Executes capability via PathwayRuntime / PatternRuntime |
| Measure | People/Capability | Measures invocation success, corrections, proficiency |
| Learn | People/Capability + EIMS | Records maturation, updates proficiency |
| Retire | People/Capability | Retires capability, notifies Operations |

---

## 7. People/Capability interaction with Organisation/Control

**Correct flow:**

```
CEO: "We should enter market X."   [strategic decision — Enterprise/CEO]
    ↓
C-Suite executive becomes accountable  [Organisation/Control]
    ↓
executive/PM determines organisational capability required
    ↓
Work created with required_capability_ids  [Organisation/Control]
    ↓
People/Capability determines capability availability/gaps
    ↓
People/Capability assigns/trains/acquires capabilities
    ↓
Work becomes executable (capabilities assigned to assigned Person/Agent)
    ↓
Operations executes  [Operations]
    ↓
Outcome/evidence returned
    ↓
Organisational assessment  [Organisation/Control]
    ↓
EIMS learning where appropriate  [Enterprise]
```

**People/Capability does NOT:**
- Decide strategic direction
- Create Work
- Assign Work
- Coordinate projects
- Execute operational work

**People/Capability DOES:**
- Assess capability availability for required capabilities
- Identify gaps
- Develop, acquire, test, qualify capabilities
- Assign capabilities to Person/Agent
- Measure proficiency and performance
- Retire capabilities
- Report capability status to Organisation/Control

---

## 8. People/Capability interaction with Operations

**Correct boundary:**

- **Operations does NOT discover or select capabilities.** It consumes capabilities that have
  already been assigned/authorised.
- **Operations executes capabilities** via its own entry points (`PathwayRuntime.invoke()`,
  `PatternRuntime.invoke_step()`, `execute_workflow()`).
- **People/Capability provides capability availability** — which capabilities exist, who is
  authorised to use them, what their proficiency is.
- **Operations may need to verify authorisation** before executing a capability (future increment).

**Current gap:** `PatternRuntime.invoke_step()` looks up any capability by ID and executes it
without checking whether the caller is authorised. This is a governance gap, not an immediate
architectural violation (authorisation checks can be added incrementally).

---

## 9. How capability requirements on Work relate to capability assignment

**Current state:** `Work.required_capability_ids` is a `list[str]`. This is a declaration only.

**Assessment:** This is **sufficient for Increment 14**. A richer model (`CapabilityRequirement`
with proficiency level, quantity, etc.) can be added later when capability matching is
implemented.

**What must happen at Work assignment time:**
1. Organisation/Control assigns Work to a Role/Person/Agent
2. People/Capability checks whether the assigned Person/Agent has the required capabilities
3. If yes: Work proceeds to `mark_work_ready()`
4. If no: People/Capability identifies the gap; Organisation/Control decides whether to
   reassign, wait, or escalate

---

## 10. Role capability requirements vs. actual people/agents

**Role.required_capability_ids** declares what the position needs.
**Person.role_ids** declares which roles a person occupies.
**Agent.fulfilled_role_ids** declares which roles an agent fulfils.

The gap is: **there is no model linking a Person/Agent's capabilities to the Role's requirements.**

People/Capability bridges this:
- When a Person occupies a Role, People/Capability checks whether the Person has the
  capabilities required by that Role
- If not, People/Capability identifies training/development needs
- If the gap cannot be filled, People/Capability reports the vacancy to Organisation/Control

This is NOT a static check. It's an ongoing capability readiness assessment.

---

## 11. Where capability matching belongs

**Capability matching belongs to People/Capability.**

Matching answers: "Given a requirement, who can fulfil it?" This is a People/Capability
question because it requires knowledge of:
- Capability definitions (People/Capability owns)
- Capability assignments (People/Capability owns)
- Capability proficiency (People/Capability owns)
- Person/Agent availability (People/Capability owns)

**Current contradiction:** `CapabilityMatcher` and `HumanSelectionMatcher` are in the
`capability_registry` package and used directly by `AssistantChatService` (Operations).
This bypasses People/Capability.

**Resolution:** People/Capability should provide a matching service. Operations and
Organisation/Control may consume the results, but the matching logic lives in People/Capability.

---

## 12. How the existing CapabilityRegistry fits into this architecture

**Current state:** `CapabilityRegistry` is in `packages/capability_registry/src/capabilities.py`.
It wraps `ConceptStore` for persistence and provides `register`, `get`, `list`, `resolve`,
`record_invocation`, `promote`.

**Assessment:** `CapabilityRegistry` is a **domain registry**, not an implementation detail.
It is the catalog of all known capabilities. It should remain in the People/Capability domain
but its persistence should not be tied to `ConceptStore` (which is an EIMS implementation).

**Future:** CapabilityRegistry should have a repository interface. The current `ConceptStore`
backing should be replaced with a capability-specific repository. ConceptStore (EIMS) may
be used for durable capability records, but CapabilityRegistry should not depend on it
directly.

---

## 13. How the existing CapabilityRequest model fits into the lifecycle

**Current state:** `CapabilityRequest` is a transient governance object for requesting NEW
capabilities. Once approved, it becomes an `EnterpriseConcept` (`kind=capability`).

**Assessment:** This is correct for NEW capability requests. It fits the lifecycle at the
**specify** phase.

**Missing:** There is no request model for:
- Requesting an EXISTING capability for a new holder (assignment request)
- Requesting capability development/training for an existing Person/Agent
- Requesting capability retirement

These can be added later. `CapabilityRequest` as-is is sufficient for Increment 14.

---

## 14. Where should training/development/acquisition live?

**People/Capability owns all three.**

- **Training:** People/Capability designs, delivers, and tracks training programs
- **Development:** People/Capability manages capability development projects
- **Acquisition:** People/Capability decides build vs. acquire, manages vendors/contracts

The output of training/development/acquisition is a CapabilityAssignment or updated
CapabilityProficiency.

---

## 15. Where should capability proficiency and evidence live?

**People/Capability owns CapabilityProficiency and evidence.**

- `CapabilityProficiency` records proficiency level, validation date, expiry, and evidence
- Evidence may include certifications, test results, observed performance data
- Proficiency may be stored in EIMS as durable enterprise knowledge (certifications,
  qualifications) but the active proficiency record lives in People/Capability

---

## 16. How this interacts with EIMS

**Capability definitions** become durable EIMS knowledge when registered (EnterpriseConcept
with `kind=capability`).

**Capability lifecycle events** (development, qualification, retirement) may become EIMS
knowledge when they have enterprise significance.

**Capability proficiency** may become EIMS knowledge when it represents institutional
knowledge (certifications, qualifications).

**Transient state** (current assignments, current availability, current proficiency for
active work) remains in People/Capability and is NOT automatically durable EIMS knowledge.

---

## 17. How this eventually maps to Paperclip

**Paperclip maps to Organisation/Control plane** (ADR-023). Paperclip provides:
- Role/Agent representation
- Work assignment and task tracking
- Coordination and meetings
- Approvals
- Organisational hierarchy
- Agent lifecycle
- Cost tracking

**Paperclip does NOT provide:**
- Capability definitions or lifecycle
- Capability assignment or proficiency
- Capability matching
- Capability governance
- EIMS

People/Capability must own capability concerns independently of Paperclip. When Paperclip
eventually provides agent lifecycle, People/Capability will use Paperclip's agent records
as one source of Agent identity, but capability assignment/proficiency remains in
People/Capability.

---

## 18. Contradictions between current code and architecture

### Contradiction 1: Person/Agent in wrong package
**Location:** `packages/organisation/src/role.py`
**Issue:** `Person` and `Agent` classes are defined in the organisation package. ADR-037 says
they belong to People/Capability.
**Severity:** High — violates ADR-037

### Contradiction 2: ConceptStore in wrong package
**Location:** `packages/capability_registry/src/concepts.py`
**Issue:** `ConceptStore` and `EnterpriseConcept` are defined in the capability_registry
package. These are EIMS/Enterprise concepts. EIMS is owned by Enterprise, not by
capability_registry.
**Severity:** High — violates plane boundaries

### Contradiction 3: CapabilityRegistry owns persistence
**Location:** `packages/capability_registry/src/capabilities.py`
**Issue:** `CapabilityRegistry.__init__` takes a `ConceptStore` and uses it directly. A
registry should not own persistence. It should use a repository interface.
**Severity:** Medium — can be addressed in Increment 14

### Contradiction 4: Capability has operational concerns
**Location:** `packages/capability_registry/src/capabilities.py` — `Capability` model
**Issue:** `Capability` has `execution_mode`, `transport`, `ai_spec`, `compiled_ref` — these
are operational execution concerns mixed into the domain model.
**Severity:** Medium — domain model should describe what a capability IS, not how it executes

### Contradiction 5: AssistantChatService bypasses People/Capability
**Location:** `packages/ai/src/chat.py`
**Issue:** `AssistantChatService` directly imports and uses `CapabilityRegistry` and
`CapabilityMatcher` from capability_registry. It should go through People/Capability for
matching.
**Severity:** Medium — Operations consuming capabilities is correct, but direct use of
CapabilityMatcher bypasses People/Capability

### Contradiction 6: No capability assignment model
**Location:** Entire codebase
**Issue:** There is no `CapabilityAssignment` or `CapabilityProficiency` model. The only
capability relationship is `required_capability_ids: list[str]` on Role and Work. There is
no way to say "Alice is assigned/qualified/authorised to use capability X."
**Severity:** High — core domain model is incomplete

### Contradiction 7: required_capability_ids is too weak
**Location:** `packages/organisation/src/role.py`, `packages/organisation/src/role.py`
**Issue:** `required_capability_ids` is just `list[str]`. There is no proficiency level,
assignment status, authorisation, or availability.
**Severity:** Low — sufficient for Increment 14; richer model can come later

### Contradiction 8: Capability lifecycle is incomplete
**Location:** `packages/capability_registry/src/capabilities.py`, architecture.md
**Issue:** Documented lifecycle is identify → specify → develop/acquire → test → register →
assign → operate → measure → learn → retire. Only register → operate → measure → learn is
implemented. No develop, acquire, test, assign, retire.
**Severity:** Medium — Increment 14 should add assignment and retirement

### Contradiction 9: CapabilityRequest only for NEW capabilities
**Location:** `packages/capability_registry/src/capability_request.py`
**Issue:** No mechanism for requesting an EXISTING capability for a new holder, or for
requesting capability development/training.
**Severity:** Low — can be added later

### Contradiction 10: Operations can execute any capability without authorisation
**Location:** `packages/workflow_runner/src/runtime.py`
**Issue:** `PatternRuntime.invoke_step()` looks up any capability by ID and executes it
without checking whether the caller is authorised.
**Severity:** Medium — governance gap; can be addressed in later increment

### Contradiction 11: EIMS learning is in the wrong package
**Location:** `packages/organisation/src/outcome.py`
**Issue:** `record_work_learning()` is in the organisation package and uses dynamic import
of `concepts`. EIMS is owned by Enterprise.
**Severity:** Low — dynamic import preserves boundary; should move to Enterprise package

---

## Proposed ADRs

### ADR-040: Capability Assignment and Proficiency Model

Capability possession by Person/Agent is modelled through explicit records, not implied
by role occupancy.

**Decision:**
1. `CapabilityAssignment` links a Person/Agent to a Capability with:
   - `person_id` or `agent_id`
   - `capability_id`
   - `assignment_type` (primary, secondary, backup)
   - `status` (active, suspended, expired)
   - `assigned_at`, `expires_at`
   - `authorised_by`
2. `CapabilityProficiency` describes how well a Person/Agent can exercise a Capability:
   - `person_id` or `agent_id`
   - `capability_id`
   - `proficiency_level` (novice, competent, proficient, expert, master)
   - `validated_at`, `valid_until`
   - `evidence`
3. These records live in the People/Capability plane
4. Operations may read them for authorisation checks but does not create/update them

### ADR-041: People/Capability Plane Package Structure

The People/Capability plane is implemented as a first-class package alongside the other
three planes.

**Decision:**
1. New package: `packages/people_capability/src/`
2. Modules:
   - `person.py` — `Person` record (moved from organisation)
   - `agent.py` — `Agent` record (moved from organisation)
   - `capability.py` — `Capability` record (currently in capability_registry)
   - `capability_assignment.py` — `CapabilityAssignment` record
   - `capability_proficiency.py` — `CapabilityProficiency` record
   - `people_capability_service.py` — service interface + in-memory implementation
3. Organisation/Control references Person/Agent by ID only (already implemented)
4. Organisation/Control does NOT import Person/Agent classes (needs verification)
5. People/Capability does NOT import Work, Role, or organisational coordination types

---

## Proposed Increment 14 Scope

### In Scope

1. **Create People/Capability plane package**
   - `packages/people_capability/src/__init__.py`
   - `packages/people_capability/src/person.py` — move `Person` from organisation
   - `packages/people_capability/src/agent.py` — move `Agent` from organisation
   - `packages/people_capability/src/capability.py` — move `Capability` from capability_registry
   - `packages/people_capability/src/capability_assignment.py` — new `CapabilityAssignment` model
   - `packages/people_capability/src/capability_proficiency.py` — new `CapabilityProficiency` model
   - `packages/people_capability/src/people_capability_service.py` — service interface + in-memory impl

2. **Create CapabilityAssignment and CapabilityProficiency models**
   - Explicit records linking Person/Agent to Capability
   - Assignment status, type, authorisation
   - Proficiency level, validation, evidence

3. **Create PeopleCapabilityService**
   - `register_person`, `get_person`, `list_persons`
   - `register_agent`, `get_agent`, `list_agents`
   - `assign_capability` (creates CapabilityAssignment)
   - `revoke_capability` (retires CapabilityAssignment)
   - `record_proficiency` (creates/updates CapabilityProficiency)
   - `get_capability_holders(capability_id)` → list of Person/Agent with active assignments
   - `get_person_capabilities(person_id)` → list of CapabilityAssignment + CapabilityProficiency
   - `find_capability_gap(required_capability_ids, person_ids)` → gap analysis

4. **Update Organisation/Control to reference Person/Agent by ID only**
   - `role.py` must NOT define Person/Agent classes
   - `organisation_control_plane.py` must import Person/Agent from people_capability (for type hints)
   - `assign_work()` already handles Person/Agent correctly; just needs correct imports

5. **Move Capability to People/Capability**
   - `Capability` model moves from `capability_registry` to `people_capability`
   - CapabilityRegistry remains in capability_registry but depends on People/Capability's Capability model

6. **Update tests**
   - All existing organisation tests must pass with moved models
   - New tests for PeopleCapabilityService
   - New tests for CapabilityAssignment and CapabilityProficiency

7. **Update architecture documentation**
   - `.kilo/context/architecture.md` updated with new package structure
   - New ADRs added

### Out of Scope

- Capability matching implementation (only the model is added)
- Capability execution changes
- Capability authorisation checks in Operations
- Paperclip integration
- EIMS expansion
- CEO implementation changes
- AssistantChatService changes
- Capability lifecycle beyond assignment and proficiency
- CapabilityRequest extensions
- Universal routing
- Training/development/acquisition implementation

---

## Answers to User's A-H Questions

### A. What the People/Capability plane actually is

The People/Capability plane is the domain plane owning the organisational workforce
(Person/Agent records) and the reusable abilities (Capability definitions) that workforce
needs to perform work. It is NOT a central service. It is NOT an execution engine. It is
a domain boundary with specific ownership: who we have, what they can do, and how well
they can do it.

### B. What it owns

- Person records (identity, employment, roles)
- Agent records (identity, marker, fulfilled roles, runtime identity)
- Capability definitions (interface, kind, lifecycle metadata)
- CapabilityAssignment (who is assigned/authorised to use what)
- CapabilityProficiency (how well someone can use a capability)
- Capability lifecycle management (all phases)
- Capability matching (determining availability)
- CapabilityRequest governance (for NEW capabilities)
- Capability gap analysis

### C. What it explicitly does NOT own

- Work
- Work assignment
- Operational execution
- EIMS
- Capability execution
- Capability discovery by Operations
- Organisational coordination
- Strategic decisions
- Authority grants

### D. The correct domain relationships

- **Role requires Capability** — Role declares position requirements
- **Person possesses Capability** — via CapabilityAssignment + CapabilityProficiency
- **Agent possesses/uses Capability** — via CapabilityAssignment + CapabilityProficiency
- **Work requires Capability** — Work declares effort requirements
- **Person occupies Role** — Person.role_ids
- **Agent fulfils Role** — Agent.fulfilled_role_ids
- **CapabilityAssignment** — explicit record of assignment/authorisation
- **CapabilityProficiency** — explicit record of skill level

### E. What happens when a role needs a capability nobody currently has

1. Organisation/Control creates Work with `required_capability_ids`
2. Work is assigned to a Role/Person/Agent
3. People/Capability checks capability availability for the assigned Person/Agent
4. If gap exists: People/Capability determines response:
   - Train/develop the Person/Agent
   - Acquire the capability externally
   - Reassign Work to someone who has the capability
   - Escalate to Organisation/Control
5. Organisation/Control decides which response to pursue
6. People/Capability executes the chosen response

### F. What happens when an existing capability needs to be transferred

1. People/Capability creates new `CapabilityAssignment` for the new holder
2. People/Capability retires the old `CapabilityAssignment` (status = expired/revoked)
3. History is preserved (assignments are never deleted)
4. CapabilityProficiency is re-evaluated for the new holder
5. Organisation/Control is informed of availability change
6. Operations is informed of new authorisation

### G. How capability discovery/matching should work without creating another God service

Capability matching is a **scoped function**, not a universal service:

1. People/Capability provides `find_capability_gap(required_capability_ids, person_ids)`
   — given requirements and candidates, return gaps
2. People/Capability provides `get_capability_holders(capability_id)` — who has this
3. People/Capability provides `get_person_capabilities(person_id)` — what does this person have
4. Operations and Organisation/Control consume these results; they do not invoke matching
   logic directly
5. The `CapabilityMatcher` protocol exists but should be consumed through People/Capability,
   not directly by Operations

The key is: matching is a **query function** with a clear input/output contract, not an
orchestrator.

### H. The smallest defensible Increment 14

1. Create `packages/people_capability/src/` package
2. Move `Person` and `Agent` from `packages/organisation/src/role.py` to
   `packages/people_capability/src/`
3. Move `Capability` from `packages/capability_registry/src/capabilities.py` to
   `packages/people_capability/src/`
4. Create `CapabilityAssignment` and `CapabilityProficiency` models
5. Create `PeopleCapabilityService` interface + in-memory implementation
6. Update Organisation/Control to import Person/Agent from people_capability
7. Update capability_registry to import Capability from people_capability
8. All 55 existing tests pass
9. New tests for PeopleCapabilityService
10. Update architecture documentation

---

## Open Questions for Increment 14 Design

None at this stage. The investigation has resolved the key architectural questions.
Increment 14 is implementation-ready.

---

## Summary

The People/Capability plane is the workforce-and-ability domain. It owns who we have
(Person/Agent), what they can do (Capability), how well they can do it (Proficiency),
and who is authorised to do what (Assignment). It provides availability and gap
information to Organisation/Control and Operations. It does not execute, coordinate,
or make organisational decisions.

The current code has contradictions (Person/Agent in wrong package, ConceptStore in wrong
package, no assignment model) that Increment 14 will correct.
