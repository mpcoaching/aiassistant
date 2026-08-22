# Increment 14 — People/Capability Plane: Architectural Correction Investigation

## Executive Summary

This investigation corrects the Increment 13 proposal before implementation. The key
corrections are:

1. **Do NOT create a PeopleCapabilityService God service.** The People/Capability domain
   should be expressed as narrow repositories and query interfaces, not as a universal
   capability router.

2. **Capability execution metadata does NOT belong on the Capability domain model.**
   `execution_mode`, `transport`, `ai_spec`, and `compiled_ref` are operational deployment
   bindings, not intrinsic capability properties. They must be separated.

3. **CapabilityRegistry should depend on a repository interface, not on ConceptStore
   directly.** ConceptStore is the current EIMS implementation. CapabilityRegistry is a
   domain registry. The two should be decoupled.

4. **Person and Agent should move to People/Capability.** This is confirmed correct.

5. **Operations authorisation is a narrow query, not a service dependency.** Operations
   needs a scoped authorisation check, not the entire People/Capability service.

6. **AssistantChatService bypass should be deferred.** Fixing it in Increment 14 would
   expand scope too much. Document it as a follow-on.

---

## 1. What exactly does People/Capability own?

People/Capability owns:

- **Person records** — human workforce identity, employment context, role occupancy
- **Agent records** — software workforce identity, marker, fulfilled roles, runtime binding
- **Capability definitions** — what abilities exist, their interface, kind, governance flags
- **CapabilityAssignment** — who is assigned/authorised to use a capability
- **CapabilityProficiency** — how well a person/agent can exercise a capability
- **Capability lifecycle governance** — identify, specify, develop/acquire, test, register,
  assign, operate (handoff), measure, learn, retire
- **Capability availability queries** — who has what, what gaps exist
- **CapabilityRequest governance** — requesting genuinely new capabilities

People/Capability does NOT own:
- Work
- Work assignment
- Operational execution
- EIMS (it uses EIMS, it does not own it)
- Execution bindings (those belong to Operations/deployment)
- Organisational coordination
- Strategic decisions
- Authority grants

---

## 2. What exactly is a Capability?

A Capability is a **reusable ability** that can be possessed, required, assigned, and
exercised. It is identified by:

- `id`, `name`, `description`
- `capability_kind` (tool, skill)
- `interface` (inputs, outputs, errors)
- `owns_durable_state` (structural property)
- `standing_contract` (governance property)

A Capability is **not**:
- an execution plan
- a deployment configuration
- a runtime binding
- a prompt template
- a compiled module reference

---

## 3. What is NOT part of Capability?

The following fields on the current `Capability` model are **NOT** intrinsic capability
properties:

| Field | What it actually is | Where it belongs |
|---|---|---|
| `execution_mode` | Operational deployment binding | `CapabilityDeployment` |
| `transport` | Infrastructure routing concern | `CapabilityDeployment` |
| `ai_spec` | AI-runtime adapter specification | `CapabilityExecutionProfile` |
| `compiled_ref` | Build artefact pointer | `CapabilityExecutionProfile` |

These four fields describe **how** a capability is invoked in a specific environment, not
**what** the capability is. The same capability can be `ai_mediated` in dev and `compiled`
in prod. The domain model must not encode deployment concerns.

---

## 4. Where do execution bindings belong?

Execution bindings belong to the **Operations plane** or a shared deployment layer.

Proposed abstraction:

```
CapabilityDeployment
    - capability_id
    - environment: str
    - execution_mode: ExecutionMode
    - transport: Transport
    - ai_spec: AiSpec | None
    - compiled_ref: CompiledRef | None
```

`CapabilityDeployment` is keyed by `(capability_id, environment)`. The same capability
can have multiple deployments. `PatternRuntime` resolves the deployment for the current
environment and reads execution metadata from there.

This is an operational/deployment concern. People/Capability may define the shape of the
deployment record, but Operations owns the runtime dispatch logic.

---

## 5. What exactly does CapabilityRegistry own?

CapabilityRegistry is a **domain catalog** — it answers "what capabilities exist?"

It owns:
- Registration, retrieval, listing, resolution by name/kind
- Maturation tracking (`record_invocation`, `promote`)
- Migration from legacy `SkillRecord` format

It does NOT own:
- Persistence (must depend on a repository interface)
- Execution dispatch
- Deployment configuration
- EIMS semantics

CapabilityRegistry should depend on a `CapabilityRepository` interface, not on
`ConceptStore` directly.

---

## 6. What exactly does ConceptStore/EIMS own?

ConceptStore (current EIMS implementation) owns:
- `EnterpriseConcept` model and its `ConceptKind` taxonomy
- Generic persistence: `upsert`, `get`, `list_by_kind`, `list_by_tag`
- `MaturationHistory`, `Provenance`, `RecognitionLevel`
- `KnowledgeStore` and `KnowledgeChunk` routing
- File-fallback with strict write semantics

EIMS is the **durable store** for enterprise knowledge. Capability definitions may be
stored in EIMS, but People/Capability must not depend on the EIMS implementation
directly.

The current conflation: `ConceptStore` lives in `packages/capability_registry/src/` and
is used as the primary persistence layer for CapabilityRegistry. This must be decoupled
via a repository interface.

---

## 7. Where do Person and Agent belong?

**Confirmed: Person and Agent belong to People/Capability.**

- `Person` — human individual with identity, employment context, role occupancy
- `Agent` — software entity with marker, fulfilled roles, runtime identity

Organisation/Control references them by ID only (`assignee_person_id`, `assignee_agent_id`,
`Role.fulfilled_role_ids` via Agent reference). Organ/Control does NOT store their lifecycle
records.

---

## 8. Where do Role relationships belong?

Role relationships belong to **Organisation/Control**:

- `Role.requires_capability_ids` — declares position requirements
- `Role.authority_ids` — declares authority grants
- `Role.reports_to` — declares reporting line
- `Person.role_ids` — declared on Person (People/Capability) but semantically references
  Organisation/Control roles
- `Agent.fulfilled_role_ids` — declared on Agent (People/Capability) but semantically
  references Organisation/Control roles

The relationship direction is important:
- Organisation/Control defines what roles exist and what they require
- People/Capability records which persons/agents occupy/fulfil which roles
- The linkage is by ID; no plane owns the other's records

---

## 9. What is CapabilityAssignment?

`CapabilityAssignment` is an explicit record that a specific Person or Agent is
assigned/authorised to use a specific Capability.

```
CapabilityAssignment:
    - id
    - capability_id
    - assignee_type: "person" | "agent"
    - assignee_id: str
    - assignment_type: "primary" | "secondary" | "backup"
    - status: "active" | "suspended" | "expired" | "revoked"
    - authorised_by: str (role or person ID)
    - assigned_at: datetime
    - expires_at: datetime | None
    - reason: str
    - metadata: dict
```

Properties:
- Assignments are **never deleted** — they are retired by status change
- History is preserved for audit and learning
- Multiple assignments can exist for the same capability/assignee over time
- Only one `active` assignment per (capability, assignee) at a time

---

## 10. What is CapabilityProficiency?

`CapabilityProficiency` records how well a Person or Agent can exercise a Capability.

```
CapabilityProficiency:
    - id
    - capability_id
    - person_id: str | None
    - agent_id: str | None
    - proficiency_level: "novice" | "competent" | "proficient" | "expert" | "master"
    - validated_at: datetime
    - valid_until: datetime | None
    - evidence: list[str] (certification IDs, test results, observation refs)
    - assessed_by: str
    - metadata: dict
```

Properties:
- Proficiency is **independent** of assignment — you can be assigned without being proficient
- Proficiency **decays** — `valid_until` enables revalidation
- Evidence is **references**, not embedded data — actual certificates/tests live in EIMS
- Multiple proficiency records can exist over time (history preserved)

---

## 11. What is the smallest correct capability-matching boundary?

Capability matching is a **scoped query function**, not a service.

The People/Capability plane provides these queries:

```python
class CapabilityQuery:
    # Who is authorised to use this capability?
    def get_capability_holders(self, capability_id: str) -> list[CapabilityHolder]:
        ...

    # What capabilities does this person/agent possess?
    def get_person_capabilities(self, person_id: str) -> list[CapabilityPossession]:
        ...
    def get_agent_capabilities(self, agent_id: str) -> list[CapabilityPossession]:
        ...

    # Given required capabilities and candidate persons/agents, what gaps exist?
    def find_capability_gap(
        self,
        required_capability_ids: list[str],
        candidate_ids: list[str],
    ) -> CapabilityGapReport:
        ...
```

Supporting types:

```python
class CapabilityHolder:
    assignee_id: str
    assignee_type: str  # "person" | "agent"
    assignment: CapabilityAssignment
    proficiency: CapabilityProficiency | None

class CapabilityPossession:
    capability_id: str
    assignment: CapabilityAssignment
    proficiency: CapabilityProficiency | None

class CapabilityGapReport:
    gaps: list[CapabilityGap]
    satisfied: list[str]

class CapabilityGap:
    capability_id: str
    required_by: str  # role_id or work_id
    missing_for: list[str]  # person/agent IDs that need it
```

**Key rule:** People/Capability answers **"who possesses what?"** It does NOT decide
**"who should do this work?"** That decision belongs to Organisation/Control / accountable
roles.

The existing `CapabilityMatcher` protocol is a **presentation-layer** concern (human
selection). It should eventually be implemented as a consumer of `CapabilityQuery`, not
as a standalone matcher.

---

## 12. How does Operations verify execution authorisation?

Operations needs a **narrow authorisation query**, not a service dependency.

Proposed abstraction:

```python
class ExecutionAuthorisationPort(Protocol):
    def is_authorised(
        self,
        actor_id: str,
        actor_type: str,  # "person" | "agent"
        capability_id: str,
    ) -> AuthorisationResult:
        ...

class AuthorisationResult:
    authorised: bool
    assignment: CapabilityAssignment | None
    proficiency: CapabilityProficiency | None
    reason: str | None
```

Properties:
- Operations **reads** authorisation state; it does NOT create or update it
- The port can be implemented by People/Capability (in-memory for now, persistent later)
- PatternRuntime receives the port via DI and checks it before execution
- This is a **query**, not a workflow — it returns a boolean, not a process

This is a **future increment** concern. Increment 14 should define the interface and
add a stub implementation, but not enforce authorisation checks in PatternRuntime yet.

---

## 13. How does Assistant interact with People/Capability without bypassing architecture?

**Current state:** `AssistantChatService` directly imports `CapabilityRegistry` and
`CapabilityMatcher` from `capability_registry`. This bypasses People/Capability.

**Assessment:** This should be **deferred to Increment 15+**. Fixing it in Increment 14
would require:
- Creating a People/Capability service interface
- Updating AssistantChatService to use it
- Updating all Assistant tests
- Ensuring the Assistant remains a role/interface, not a capability matcher

The risk of fixing it now is that we would create a PeopleCapabilityService that is
shaped by Assistant's needs rather than by the domain's structure.

**Deferral condition:** Increment 14 should document that AssistantChatService's direct
use of `CapabilityRegistry` and `CapabilityMatcher` is a known architectural bypass that
will be corrected when People/Capability's query interface is stable.

---

## 14. What dependencies are permitted between the four planes?

```
Enterprise
    |  reads from (via EIMS interface)
    v
EIMS (ConceptStore — current implementation)
    ^
    |  writes durable knowledge to
    |
Organisation / Control
    |  reads from (capability availability, people records)
    v
People / Capability
    |  executes via (authorised capabilities)
    v
Operations
```

Specific rules:

| From | To | Allowed | Prohibited |
|---|---|---|---|
| Enterprise | EIMS | Read/write durable knowledge | Execute operational work |
| Enterprise | Organisation/Control | Read organisational context | Own roles, authority, work |
| Enterprise | People/Capability | Read workforce/capability state | Own people, capabilities |
| Organisation/Control | People/Capability | Read capability availability, people IDs | Own capability lifecycle, people lifecycle |
| Organisation/Control | Operations | Hand off work (mark_work_ready) | Execute work, own capabilities |
| People/Capability | EIMS | Write durable capability knowledge | Own EIMS |
| People/Capability | Organisation/Control | Read role requirements, work requirements | Own roles, authority, work |
| People/Capability | Operations | Provide capability bindings | Execute capabilities, own workflows |
| Operations | People/Capability | Query authorisation (ExecutionAuthorisationPort) | Own capability lifecycle, people lifecycle |
| Operations | Organisation/Control | Read work state, role context | Own roles, authority |

---

## 15. Which contradictions should be corrected now?

| # | Contradiction | Correct in I14? | Reason |
|---|---|---|---|
| 1 | Person/Agent in wrong package | **Yes** | Core to establishing People/Capability as a domain plane |
| 2 | ConceptStore in wrong package | **Partial** | Move ConceptStore location in I15; add repository interface in I14 |
| 3 | CapabilityRegistry owns persistence | **Yes** | Add repository interface in I14 |
| 4 | Capability has operational concerns | **Yes** | Separate execution bindings in I14 |
| 5 | AssistantChatService bypass | **No** | Defer to I15; document as known bypass |
| 6 | No capability assignment model | **Yes** | Core to People/Capability ownership |
| 7 | required_capability_ids too weak | **No** | Sufficient for now; richer model later |
| 8 | Capability lifecycle incomplete | **Partial** | Add assignment/retirement in I14; full lifecycle later |
| 9 | CapabilityRequest only for NEW | **No** | Defer; existing model sufficient |
| 10 | Operations unauthorised execution | **Partial** | Define authorisation port in I14; enforce later |
| 11 | EIMS learning in wrong package | **No** | Dynamic import preserves boundary; move in I15 |

---

## 16. Which contradictions should explicitly be deferred?

- **Contradiction 5** (Assistant bypass) — Defer to Increment 15
- **Contradiction 7** (required_capability_ids too weak) — Sufficient for current needs
- **Contradiction 9** (CapabilityRequest only for NEW) — Existing model sufficient
- **Contradiction 11** (EIMS learning in wrong package) — Dynamic import is acceptable interim

---

## 17. What is the smallest implementation that proves the architecture?

The proof is:

1. `Person` and `Agent` live in `people_capability` package
2. `Capability` domain model lives in `people_capability` package, stripped of execution
   metadata
3. `CapabilityAssignment` and `CapabilityProficiency` models exist and are testable
4. `CapabilityRegistry` depends on a `CapabilityRepository` interface, not `ConceptStore`
5. `ConceptStoreCapabilityRepository` adapter bridges the interface to existing ConceptStore
6. `CapabilityDeployment` separates execution bindings from domain model
7. `ExecutionAuthorisationPort` interface defined (stub implementation)
8. All 55 existing tests pass
9. New tests prove the domain model and boundaries

---

## Proposed ADRs

### ADR-042: Capability Execution Binding Separation

The `Capability` domain model must not carry operational execution metadata.

**Decision:**
1. `Capability` domain model retains: `id`, `name`, `description`, `capability_kind`,
   `interface`, `owns_durable_state`, `standing_contract`
2. `execution_mode`, `transport`, `ai_spec`, `compiled_ref` move to `CapabilityDeployment`
3. `CapabilityDeployment` is keyed by `(capability_id, environment)`
4. `PatternRuntime` resolves deployment for current environment
5. People/Capability may define the shape of deployment records; Operations owns runtime
   dispatch

### ADR-043: Capability Repository Interface

CapabilityRegistry must not depend on ConceptStore (EIMS implementation) directly.

**Decision:**
1. Define `CapabilityRepository` protocol with `upsert`, `get`, `list_by_kind`,
   `record_invocation`
2. `CapabilityRegistry.__init__` accepts `CapabilityRepository | None`
3. `ConceptStoreCapabilityRepository` adapter wraps `ConceptStore` for now
4. Future: EIMS can provide its own repository implementation without changing
   CapabilityRegistry

---

## Revised Increment 14 Scope

### In Scope

1. **Create `packages/people_capability/src/` package skeleton**
2. **Move `Person` and `Agent` from `packages/organisation/src/role.py`**
   - Update all imports in organisation package
   - Update all tests
3. **Move `Capability` from `packages/capability_registry/src/capabilities.py`**
   - Strip `execution_mode`, `transport`, `ai_spec`, `compiled_ref`
   - Keep `owns_durable_state`, `standing_contract`
4. **Create `CapabilityAssignment` and `CapabilityProficiency` models**
5. **Create `CapabilityRepository` interface**
6. **Create `ConceptStoreCapabilityRepository` adapter**
7. **Update `CapabilityRegistry` to depend on `CapabilityRepository`**
8. **Create `CapabilityDeployment` for execution bindings**
9. **Define `ExecutionAuthorisationPort` interface** (stub implementation)
10. **Update all imports and tests**
11. **Add architectural guardrail tests**
12. **Update architecture documentation**

### Out of Scope

- AssistantChatService bypass fix (Increment 15)
- ConceptStore package relocation (Increment 15)
- Enforcing authorisation in PatternRuntime (Increment 15+)
- Capability matching implementation (model only in I14)
- Capability lifecycle beyond assignment/proficiency
- Paperclip integration
- EIMS expansion
- CEO implementation changes
- Universal routing
- Complete authorisation framework

---

## Answers to User's A-H Questions (Corrected)

### A. What the People/Capability plane actually is

The workforce-and-ability domain plane. Owns who we have (Person/Agent), what they can do
(Capability definitions), how well they can do it (Proficiency), and who is authorised to
do what (Assignment). Provides availability and gap information to other planes. Does not
execute, coordinate, or make organisational decisions.

### B. What it owns

- Person records
- Agent records
- Capability definitions (domain model only — no execution metadata)
- CapabilityAssignment
- CapabilityProficiency
- Capability lifecycle governance
- Capability availability queries (`CapabilityQuery`)
- CapabilityRequest governance
- CapabilityRepository interface

### C. What it explicitly does NOT own

- Work, Work assignment, operational execution, EIMS, execution bindings, organisational
  coordination, strategic decisions, authority grants

### D. The correct domain relationships

- Role requires Capability → `Role.required_capability_ids`
- Work requires Capability → `Work.required_capability_ids`
- Person possesses Capability → `CapabilityAssignment` + `CapabilityProficiency`
- Agent possesses Capability → `CapabilityAssignment` + `CapabilityProficiency`
- Person occupies Role → `Person.role_ids`
- Agent fulfils Role → `Agent.fulfilled_role_ids`

### E. What happens when a role needs a capability nobody currently has

Capability gap. People/Capability reports the gap to Organisation/Control. Organisation/Control
decides: train, acquire, reassign, or escalate. People/Capability executes the chosen response.

### F. What happens when an existing capability needs to be transferred

People/Capability creates new CapabilityAssignment, retires old one (status=revoked),
preserves history, re-evaluates proficiency, informs Organisation/Control and Operations.

### G. How capability discovery/matching should work

Narrow query interface (`CapabilityQuery`). Not a universal service. Answers "who
possesses what?" — does not decide "who should do this work?"

### H. The smallest defensible Increment 14

1. Create `people_capability` package
2. Move Person, Agent, Capability (domain-only)
3. Create CapabilityAssignment, CapabilityProficiency
4. Create CapabilityRepository interface + adapter
5. Create CapabilityDeployment for execution bindings
6. Define ExecutionAuthorisationPort interface
7. Update all imports/tests
8. All 55 existing tests pass
9. Update architecture docs

---

## Note on `.kilo/context/architecture.md`

The architecture.md update from Increment 13 could not be applied due to file permission
restrictions. The Increment 14 investigation report and ADRs have been created. The
architecture.md should be updated to reflect:
- ADR-040 and ADR-041 additions
- ADR-042 and ADR-043 additions
- Updated People/Capability plane description
- New CapabilityAssignment/CapabilityProficiency glossary entries
- Updated Import Model to include people_capability
- Current Implementation State updates
