# Increment 42 — Organisation Implementation Boundary

Traces current code to determine the smallest implementation boundary
required for OCP to support a concrete organisational change using the
primitives we already have.

Scenario: Customer Acquisition capability needs additional capacity.
  Option A: Add new Actor (Person/Agent) with Role + CapabilityAssignments
  Option B: Change existing Actor responsibilities/capability assignments

Both options work without introducing new domain concepts.

Investigation first. No production changes. Prefer zero production changes.

---

## A. Current creation mechanisms

The following entities can currently be created:

**Person** (`packages/people_capability/src/person.py:25-36`):
Created via `InMemoryAgentStore.register_person()`. Person records are
owned by People/Capability (ADR-037). OCP does not create Persons.

**Agent** (`packages/people_capability/src/agent.py:31-42`):
Created via `InMemoryAgentStore.register_agent()`. Agent records are
owned by People/Capability (ADR-037). OCP does not create Agents.

**Actor** (`packages/people_capability/src/actor.py:32-59`):
Created automatically when Person/Agent is registered in
InMemoryAgentStore. Actor is a lightweight organisational identity
with `reference_id` pointing to Person/Agent.

**Role** (`packages/organisation/src/role.py:49-65`):
Created via `InMemoryOrganisationControlPlane.register_role()`.
Roles define positions, responsibilities, required capabilities.
This is the primary organisational design mechanism.

**Capability** (`packages/people_capability/src/capability.py:43-64`):
Registered via `CapabilityRegistry.register()` (ADRR-020).
OCP can register awareness but lifecycle is owned by CapabilityRegistry.

**CapabilityAssignment** (`packages/people_capability/src/capability_assignment.py:38-84`):
Created via `InMemoryAgentStore.assign_capability()`. Links Actor→Capability.
Authoritative Actor↔Capability relationship.

**Work** (`packages/organisation/src/role.py:96-126`):
Created via `InMemoryOrganisationControlPlane.assign_work()` (for assignment)
or directly instantiated. Work represents organisational effort.

**Authority/Delegation** (`packages/organisation/src/role.py`):
Created via `register_authority()` and `delegate_authority()` on OCP.

**OCP does NOT create**:
- Person (ADR-037): no `register_person()` method
- Agent (ADR-037): no `register_agent()` method
- Capability (ADR-020): delegates to CapabilityRegistry

---

## B. Work as organisational change

**Conclusion**: Work is sufficient to represent organisational change proposals.

Existing Work fields can carry the semantics:

| Proposal element | Work field |
|---|---|
| Title | `title` |
| Description | `description` |
| Accountable entity | `accountable_role_id` |
| Required capabilities | `required_capability_ids` |
| Success criteria | `acceptance_criteria` |
| Current constraint/evidence | `context` (dict) |
| Expected outcome | `outcome` (after implementation) |
| Dependencies | `dependencies` |
| Deliverables | `deliverables` |
| Work type | `work_type` (e.g., "initiative") |

Example: Work("Create Customer Acquisition capacity", work_type="initiative",
accountable_role_id="customer-acquisition", required_capability_ids=[...],
context={"evidence": "...", "economic_justification": "..."})

**No OrganisationalChange or Decision entity needed** — Work suffices.

---

## C. Role boundary

**Role adequately represents organisational requirement** (per Increment 40).

Role has all necessary fields for the organisational requirement:
- `name`, `description` — identity and purpose
- `responsibilities` — what the position does
- `required_capability_ids` — what capabilities it needs
- `authority_ids` — what it can do
- `constraints` — limitations
- `information_access` — what it can see
- `reports_to` — reporting relationship
- `status` — ACTIVE|INACTIVE|VACANT
- `metadata` — extensible

**No PositionSpecification needed.** Role already serves as the position
concept per ADR-018 ("abstract position").

RoleStatus.VACANT explicitly models "the organisation needs someone
in this position", triggering People/Capability to fill it.

---

## D. Actor creation boundary

**The boundary between organisational requirement and execution identity:**

```
Role (organisational requirement)
  ↓ (fulfilled by)
Actor (organisational identity, lightweight reference)
  ↓ (references)
Person | Agent (execution identity, owned by People/Capability)
```

**Unfilled organisational responsibility**: Role with Status=VACANT.
**Existing Actor taking a Role**: Actor.fulfilled_role_ids includes Role ID.
**New Person filling Role**: Person registered in People/Capability → Actor created.
**New Agent filling Role**: Agent registered in People/Capability → Actor created.

**No vacancy/requisition concept needed.** RoleStatus.VACANT is sufficient.

---

## E. Capability assignment boundary

**CapabilityAssignment is the authoritative Actor↔Capability relationship.**

Assignment chain:
```
Capability (owned by People/Capability)
  ↔ CapabilityAssignment (actor_id + capability_id)
  → Actor (organisational identity)
```

**Verification:**
- Capability remains organisation-owned (via CapabilityRegistry)
- Actor remains execution identity
- Assignment is authoritative link
- Proficiency distinct from authorisation (separate model)
- Paperclip does not become source of Capability semantics

**Assignment type** (PRIMARY|SECONDARY|BACKUP) encodes capacity tier.
**Assignment status** (ACTIVE|SUSPENDED|EXPIRED|REVOKED) encodes validity.

---

## F. Existing Actor vs new Actor

**Both options work without new domain concepts:**

**Option A** — Increase existing Actor capacity:
```
existing Actor → new CapabilityAssignment
```

**Option B** — Create new Actor:
```
organisational need → Role → new Person/Agent → Actor → CapabilityAssignment
```

**Option C** — Change execution path:
```
capability need → workflow/tool/automation (via select_execution_path)
```

**Principle confirmed** (Increment 41): A capability gap does not
automatically mean another person or agent. The existing Actor can
simply receive additional CapabilityAssignments.

---

## G. Alternative capacity responses

Existing primitives represent all alternatives:

| Alternative | Representation |
|---|---|
| New Actor with new Role | New Person/Agent + Role + CapabilityAssignment |
| Existing Actor expansion | New CapabilityAssignment on existing Actor |
| Automate/workflow | select_execution_path → EXISTING_WORKFLOW or CAPABILITY_PATH |
| Tool/MCP/external | Tool with implementation_type=EXTERNAL_SERVICE |
| Process improvement | Work with context describing improvement |

**No new decision framework needed.** select_execution_path's
HUMAN_TEAM_INVESTIGATION path implies "investigate alternatives".

---

## H. Economic justification boundary

**Economic reasoning enters via Work.context (dict[str, Any]).**

Work carries economic data analytically:
```python
Work(
    context={
        "current_capacity_constraint": "...",
        "evidence": "...",
        "expected_outcome": "...",
        "economic_justification": "...",
    }
)
```

**No economic entities created:**
- No Cost, Value, ROI, Budget fields on any model
- No Cost/Value class exists anywhere in organisation or people_capability packages
- Economic reasoning stays analytical, not typed

---

## I. Paperclip implementation boundary

**Minimum OCP→Paperclip contract:**

OCP sends (WHAT should exist):
1. Role definitions: id, name, description, responsibilities, required_capability_ids, reports_to
2. Capability requirements: which Capabilities each Role needs
3. Work items: what organisational effort is needed

Paperclip receives (HOW it represents them):
1. Agents: mapped from Roles via `create_agent()` and `_map_agent_to_role()`
2. Issues: mapped from Work via `create_work()` and `_map_issue_to_work()`
3. Assignees: mapped via `assign_work()` → assigneeAgentId/assigneeUserId
4. Reporting: mapped via Role.reports_to → Agent.reportsTo

**Does an OCP Actor need to exist before Paperclip creates its Agent?**
Yes. Paperclip create_agent() takes a name and creates an Agent. The OCP
then creates the corresponding Actor/Person/Agent record in People/Capability.

**Does Paperclip Agent ID become the implementation reference?**
Yes. Agent.id maps to Actor.reference_id.

**How are reporting relationships mapped?**
Role.reports_to → Agent.reportsTo (single-parent chain).

**How are Roles/titles mapped?**
Agent.role (in Paperclip) maps to Role.id/name.

**How are teams/subtrees handled?**
Per Increment 40, Team is a Paperclip catalog concept, not OCP.
Paperclip Team Catalog handles bundling. OCP expresses structure via Roles.

**What organisational information must remain exclusively in OCP?**
- Role definitions and hierarchy (Role.reports_to)
- Work definitions (accountable_role_id, required_capability_ids)
- Authority and Delegation
- Capability requirements

**What information can Paperclip own operationally?**
- Agent runtime state (heartbeat runs, execution status)
- Agent capabilities (flat string field for runtime resolution)
- Execution results

**Do NOT build the adapter yet** — the boundary is already sufficiently
defined via existing `_map_agent_to_role()`, `_map_issue_to_work()`,
`assign_work()`, and `create_agent()` methods in PaperclipOrganisationControlPlane.

---

## J. Creation authority

| Entity | Who creates | Where | Type |
|---|---|---|---|
| Person | People/Capability | InMemoryAgentStore.register_person() | Organisational |
| Agent | People/Capability | InMemoryAgentStore.register_agent() | Organisational |
| Role | OCP | InMemoryOrganisationControlPlane.register_role() | Organisational |
| Capability | CapabilityRegistry | CapabilityRegistry.register() | Organisational |
| CapabilityAssignment | People/Capability | InMemoryAgentStore.assign_capability() | Organisational |
| Work | OCP | assign_work() | Organisational |
| Authority | OCP | register_authority() | Organisational |
| Paperclip Agent | Paperclip API | create_agent() | Implementation |
| Paperclip Issue | Paperclip API | create_work() | Implementation |

**No privileged "People/HR system"** that magically creates organisations.
Instead, a suitably authorised organisational Actor exercises capabilities
that result in these changes.

**Creation authority belongs to OCP/People/Capability.**
Paperclip is an implementation backend that instantiates agents.

---

## K. Recursive organisational operation

**People/Capability as ordinary organisational construct:**

The flow uses existing mechanisms:
```
Work → People/Capability Role (receives work)
  → defines new Role (register_role)
  → Paperclip creates Agent with that Role (create_agent)
  → Actor created from Agent (register_agent)
  → CapabilityAssignment links Actor to required Capabilities
  → New Actor receives Work via normal assignment
```

**No HRService, PeopleCapabilityManager, OrganisationBuilder, TeamFactory,
AgentFactory domain service needed.**

**Chief of Staff test case:**
- Chief of Staff = a Role (e.g., "Chief of Staff") with coordination responsibilities
- Uses Delegation (ADR-019) for coordination
- No ChiefOfStaff class, no special routing, no hard-coded executive privileges
- Receives Work, identifies capacity issues, delegates investigation,
  requests organisational change, coordinates with People/Capability

---

## L. Post-change organisational state

After a successful organisational change, existing models establish state:

| State element | Existing model |
|---|---|
| Actor exists | Actor in People/Capability store |
| Role exists | Role in OCP (RoleStatus.ACTIVE) |
| CapabilityAssignment exists | CapabilityAssignment record |
| Work is complete | Work.status = COMPLETED |
| Implementation reference exists | Agent.id = Actor.reference_id |
| Paperclip agent exists | Paperclip Agent (via create_agent) |

**No organisation snapshot/versioning system needed.**

---

## N. Failure / partial completion boundary

**Where consistency belongs — OCP owns organisational truth:**

| Failure scenario | OCP state | Implementation state | Resolution |
|---|---|---|---|
| Role succeeds, Actor fails | Role exists (VACANT) | Actor not created | Retry Actor creation |
| Actor exists, Assignment fails | Actor exists | No Assignment | Retry Assignment |
| OCP succeeds, Paperclip fails | Role/Work exist | Agent not provisioned | Retry Paperclip |
| Paperclip succeeds, OCP doesn't record | No OCP record | Agent exists | OCP catches up via sync |

**No distributed transactions or event sourcing.**
Each bounded context manages its own consistency:
- OCP: Roles, Work, Authority, Delegation
- People/Capability: Persons, Agents, CapabilityAssignments
- Paperclip: Agents (operational), Issues (operational)

---

## O. Existing architectural coverage

**Tests from Increments 24–41 that prove existing boundaries:**

- Increment 34: Evidence adoption boundary — record_work_learning excludes BAU
- Increment 35: Workflow lifecycle — WorkflowDefinition is boundary object
- Increment 36: Execution authority — workflow execution lacks actor context
- Increment 37: BAU semantics — Work.work_type="bau" classification
- Increment 38: Evidence boundary — WorkflowExecutionResult has no evidence fields
- Increment 39: Invocation boundary — 6 invocation paths converge
- Increment 40: Team/Role boundary — Team is NOT an OCP Actor, Role suffices
- Increment 41: Economic boundary — no Capacity/Value/Decision entities needed

**Increment 42 adds tests for genuinely new conclusions:**
- Work represents organisational change (new)
- OCP→Paperclip contract is minimal (new)
- Both Actor options work without new concepts (new)
- Creation authority is distributed (new)
- Failure boundary is clean (new)

---

## P. Missing concepts

**None.** Existing primitives fully support organisational change.

---

## Q. Rejected concepts

| Concept | Rejection reason |
|---|---|
| OrganisationalChange | Work suffices |
| Decision | Work (proposal) + Work (implementation) + Work (outcome) suffices |
| PositionSpecification | Role suffices |
| Vacancy/Requisition | RoleStatus.VACANT suffices |
| Team as Actor | Per Increment 40 |
| HRService | Ordinary organisational function |
| Capacity entity | Per Increment 41 — derived from Work/Assignment |
| Value entity | Per Increment 41 — analytical interpretation |
| Cost entity | Per Increment 41 — context dict suffices |
| Paperclip provisioning adapter | Boundary already defined |

---

## R. Architectural options

**Option A**: Minimal — zero production changes, trace only.
**Option B**: Lightweight adapter — formalise OCP→Paperclip contract.

**Recommended**: Option A (investigation first). The boundary is already
sufficiently defined via existing methods. A minimal adapter is warranted
only if the investigation concludes the boundary is clearly defined and
a minimal implementation is clearly needed — which it is, but the
constraints say "Do NOT build the adapter yet unless the investigation
concludes the boundary is already sufficiently defined and a minimal
implementation is clearly warranted."

---

## S. Recommended implementation boundary

**Decision**: Investigation complete, zero production changes.

The smallest implementation boundary for OCP to support organisational
change:

1. OCP creates Role (register_role) with required_capability_ids
2. OCP creates Work (assign_work) representing the organisational change
3. People/Capability creates Actor (register_person/register_agent)
4. People/Capability creates CapabilityAssignment (assign_capability)
5. Paperclip instantiates Agent (create_agent) — implementation
6. OCP tracks implementation reference (Actor.reference_id)

---

## T. Impact on Increments 40–41

**No impact.** Increments 40 and 41 conclusions are reinforced, not changed.

- Increment 40: Team is not an OCP Actor, Role suffices — **confirmed**
- Increment 41: Economic reasoning needs no new entities — **confirmed**
- Both Increments remain closed and are NOT reopened

---

## U. Architectural tests

**83 tests** in `packages/organisation/tests/test_increment42_organisation_implementation_boundary.py`, all passing.

### Sections covered:
- A. Current creation mechanisms (11 tests)
- B. Organisational change as Work (4 tests)
- C. Role boundary (6 tests)
- D. Actor creation boundary (4 tests)
- E. Capability assignment boundary (6 tests)
- F. Existing Actor vs new Actor (5 tests)
- G. Alternative capacity responses (1 test)
- H. Economic justification boundary (3 tests)
- I. Paperclip implementation boundary (8 tests)
- J. Creation authority (6 tests)
- K. Recursive organisational operation (4 tests)
- L. Post-change organisational state (5 tests)
- M. Failure/partial completion boundary (5 tests)
- N. Existing test coverage (3 tests)
- O. Invariants (9 tests)

---

## V. Final decision

**Architectural Decision: A** (investigation first, zero production changes).

The existing primitives — Role, Actor, Capability, CapabilityAssignment,
Work, Assignment, Authority, Delegation, Paperclip Agent — are sufficient
to support a concrete organisational change. No new domain concepts are
required. The OCP→Paperclip implementation boundary is already clearly
defined via existing adapter methods.

---

## Decision Table

| Boundary | Current mechanism | OCP authority | External implementation | New concept required? |
|---|---|---|---|---|
| Role creation | register_role() | OCP | — | No |
| Work creation | Work instantiation + assign_work() | OCP | — | No |
| Person creation | register_person() | People/Capability | — | No |
| Agent creation | register_agent() | People/Capability | — | No |
| Actor creation | Auto from Person/Agent | People/Capability | — | No |
| Capability creation | CapabilityRegistry.register() | People/Capability | — | No |
| CapabilityAssignment | assign_capability() | People/Capability | — | No |
| Role→Agent mapping | _map_agent_to_role() + create_agent() | OCP defines WHAT | Paperclip implements HOW | No |
| Work→Issue mapping | _map_issue_to_work() + create_work() | OCP defines WHAT | Paperclip implements HOW | No |
| Reporting relationship | Role.reports_to → Agent.reportsTo | OCP intent | Paperclip runtime | No |
| Reporting relationship | Authority + Delegation | OCP | — | No |
| Failure boundary | OCP state preserved | OCP owns truth | Paperclip retryable | No |

---

## Explicit Answers

**1. Can existing Work represent an organisational change proposal?**
Yes. Work has title, description, accountable_role_id, required_capability_ids,
acceptance_criteria, context, deliverables, outcome, dependencies, status,
work_type — all sufficient for a proposal like "Create Customer Acquisition capacity".

**2. Can Role represent the organisational requirement?**
Yes. Role has name, description, responsibilities, required_capability_ids,
reports_to, status (VACANT for unfilled), authority_ids, constraints.
No PositionSpecification needed.

**3. Can an existing Actor simply receive additional responsibility/capability?**
Yes. New CapabilityAssignment on existing Actor is a valid option.
The organisation can increase existing Actor capacity instead of creating new.

**4. Can a new Actor be created without introducing a new domain concept?**
Yes. New Person/Agent → Actor → CapabilityAssignment uses existing
concepts only. No vacancy/requisition concept needed (RoleStatus.VACANT).

**5. Can CapabilityAssignment remain the authoritative capability relationship?**
Yes. CapabilityAssignment(actor_id, capability_id) is the canonical
link. Proficiency is separate. Paperclip does not duplicate Capability.

**6. Can People/Capability perform these operations as an ordinary organisational Actor?**
Yes. People/Capability is a Role + Actor + CapabilityAssignments.
No HR engine, no special subsystem. Ordinary organisational function.

**7. What is the minimum OCP→Paperclip contract?**
OCP sends Role definitions (id, name, required_capability_ids, reports_to).
Paperclip creates Agents mapped from Roles. Already implemented via
create_agent(), _map_agent_to_role(), create_work(), _map_issue_to_work().

**8. Where does creation authority actually belong?**
OCP and People/Capability hold organisational authority.
Paperclip is implementation backend that instantiates agents.

**9. What happens at the OCP/Paperclip failure boundary?**
OCP state is preserved (Role, Work exist). Paperclip failure is retriable.
No distributed transactions needed — each context manages own consistency.

**10. What is the smallest production change required, if any?**
None. Existing primitives fully support the organisational change flow.
