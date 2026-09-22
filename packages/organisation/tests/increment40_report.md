# Increment 40 — Organisational Team, Role & People/Capability Function Boundary

Investigate the organisational model required to support:
- C-Suite/Chief-of-Staff layer directing specialist teams
- People/Capability function determining capacity and causing creation/configuration of people/agents/teams
- Team vs Actor vs Role semantics
- Paperclip as implementation

---

## A. Current Actor Model

**Definition**: `packages/people_capability/src/actor.py:32-59`

```
Actor(id, name, actor_type: ActorType{PERSON|AGENT}, reference_id, marker,
      fulfilled_role_ids: list[str], organisation_id, metadata, created_at, updated_at)
```

**Subtypes** (both in people_capability plane):
- **Person** (`person.py:25-36`): id, name, email, status (ACTIVE|INACTIVE|ON_LEAVE), role_ids: list[str], employment_context, metadata
- **Agent** (`agent.py:31-42`): id, name, marker (AI|HUMAN|HYBRID), status (ACTIVE|INACTIVE|DEPROVISIONED), fulfilled_role_ids, runtime_identity, metadata

**Key design** (ADR-037): Actor is a unified organisational identity. Lightweight reference linking to Person/Agent via `reference_id`. Person/Agent records owned by People/Capability. Organisation references by ID only. OrganisationControlPlane does NOT store Person/Agent records.

**ActorType enum** at `actor.py:25-30`: only PERSON and AGENT.

---

## B. Current Role Model

**Definition**: `packages/organisation/src/role.py:49-65`

```
Role(id, name, description, responsibilities: list[str], authority_ids: list[str],
     constraints: list[str], information_access: list[str], reports_to: str|None,
     status: RoleStatus{ACTIVE|INACTIVE|VACANT}, required_capability_ids: list[str], metadata)
```

**Per ADR-018**: Role is an abstract position (template/blueprint), not a person or agent. A Role is occupied by a Person or fulfilled by an Agent via `Person.role_ids` and `Agent.fulfilled_role_ids`. Same Role can be occupied by different Persons over time. Capabilities assigned to Roles via `required_capability_ids`.

**Per ADR-034**: Role is the accountability unit for Work.

**Related records in same file** (`role.py`):
- **Authority** (68-80): permission grant within a scope (grantor_role_id, grantee_role_id)
- **Delegation** (83-93): record of authority delegation between roles
- **Work** (96-126): instance of assigned effort, accountable to a Role
- **Assignment** (129-141): link between Work and assignee
- **OrgContext** (144-152): current organisational context

---

## C. Current Capability Model

**Definition**: `packages/people_capability/src/capability.py:43-64`

```
Capability(id, name, description, capability_kind: CapabilityKind{TOOL|SKILL},
           status: CapabilityStatus{DRAFT|ACTIVE|DEPRECATED}, interface: CapabilityInterface,
           owns_durable_state, standing_contract, tags, owner, created_by, created_at,
           updated_at, metadata, payload)
```

**CapabilityRegistry** (`capability_registry/src/capabilities.py:22-94`): Owns lifecycle (register, get, list, promote). Delegates persistence to CapabilityRepository.

**Distinct from Skill and Tool** (ADR-035):
- **Skill** (`skill.py:22-50`): `id, capability_id, name, description, tags, method, tool_ids` — a learned reusable METHOD for exercising a Capability
- **Tool** (`tool.py:38-64`): `id, name, description, implementation_type{PYTHON|MCP|HTTP_API|PAPERCLIP|LANGGRAPH|EXTERNAL_SERVICE}, implementation_ref, supports, tags` — an executable RESOURCE

**ADR-020**: Capability ownership by People/Capability.
**ADR-040**: CapabilityAssignment is authoritative link between Actor and Capability.

---

## D. Current Assignment Model

**CapabilityAssignment** (`packages/people_capability/src/capability_assignment.py:38-84`):
```
CapabilityAssignment(id, capability_id, actor_id, skill_ids: list[str], tool_ids: list[str],
                     assignee_type, assignee_id, assignment_type{PRIMARY|SECONDARY|BACKUP},
                     status{ACTIVE|SUSPENDED|EXPIRED|REVOKED}, authorised_by, assigned_at,
                     expires_at, reason, metadata)
```

Links Actor (actor_id) → Capability (capability_id). Optional Skill/Tool references.

**Organisational Assignment** (`role.py:129-141`):
```
Assignment(id, work_id, assignee_type, assignee_id, status{PROPOSED|ACCEPTED|DECLINED|COMPLETED}, assigned_at, accepted_at, notes)
```

Links Work → assignee.

**CapabilityProficiency** (`capability_proficiency.py:30-58`): describes HOW WELL an Actor exercises a Capability (per ADR-040).

---

## E. Current Work Assignment Semantics

**Work** (`role.py:96-126`): accountable to a Role (`accountable_role_id`). Not a capability, not an execution unit. Has fields: `assignee_role_id`, `assignee_actor_id`, `assignee_person_id`, `assignee_agent_id`, `required_capability_ids`, `coordinating_role_id`, `requested_by_role_id`, `parent_work_id`, `acceptance_criteria`, `deliverables`, `outcome`, `dependencies`.

**assign_work** (`organisation_control_plane.py:285-324`): accepts `Actor | Role | Person | Agent`. Sets appropriate assignee fields based on type.

**Work lifecycle** (per ADR-034, ADR-039): PENDING → ASSIGNED → READY → IN_PROGRESS → COMPLETED/FAILED/CANCELLED/ESCALATED.

**Delegation** (ADR-019): Authority delegation between Roles via Delegation records. Work flows through authority chain.

---

## F. Team-Related Concepts Already Present

**In OCP domain**: NONE. No Team concept exists in any organisation, capability, workflow, or contract package.

**In Paperclip**: Team exists ONLY as `@paperclipai/teams-catalog` catalog/install concept:
- Location: `operational/paperclip/packages/teams-catalog/`
- `CatalogTeam` type (`src/types.ts`): id, key, kind ("bundled"|"optional"), category, slug, name, description, path, entrypoint ("TEAM.md"), schema, defaultInstall, counts, rootAgentSlugs, agentSlugs, projectSlugs, requiredSkills, envInputs, sourceRefs, files, trustLevel, compatibility, contentHash
- Teams defined via `TEAM.md` frontmatter with: name, description, schema, manager, includes
- **NO `teams` database table** — Team is an install-time catalog abstraction
- Installed state tracked via agent `metadata.paperclip.catalogTeam` provenance
- **4 shipped teams**: core-exec-team, product-engineering, product-design, content-machine

**No group/department/unit/collective concepts exist** anywhere in the codebase. The only hierarchy mechanism is `Agent.reportsTo` (single-parent chain).

**`HUMAN_TEAM_INVESTIGATION`** in `execution_path.py` is an ExecutionPath enum value meaning "human team must investigate" — NOT a Team entity.

---

## G. Actor vs Team Analysis

### Investigation Questions and Answers:

| Question | Answer | Evidence |
|----------|--------|----------|
| Can a Team be responsible for Work? | No OCP mechanism | Work has `accountable_role_id`, not team_id. No Team concept in OCP to be responsible. |
| Can a Team be assigned a Capability? | No | CapabilityAssignment links Actor→Capability. No Team field exists. |
| Can a Team exercise a Capability? | No | `assign_work` accepts Actor\|Role\|Person\|Agent, not Team. |
| Can a Team have Proficiency? | No | CapabilityProficiency links Actor→Capability. No Team concept. |
| Can a Team be the assignee of Work? | No | Work.assignee fields: role_id, actor_id, person_id, agent_id. No team_id. |
| Can another Actor delegate Work to a Team? | No | Delegation is between Roles. assign_work takes Actor\|Role\|Person\|Agent. |
| Can a Team contain Persons/Agents/Teams? | No containment concept | ActorType enum has PERSON\|AGENT only. No parent-child containment in OCP. |
| Does a Team need its own identity? | Not in OCP | Paperclip's Team is a catalog/install config, not a domain entity. |
| What does "responsible for outcome" mean? | Applied to Role | `accountable_role_id` on Work expresses accountability. Role is the unit. |

### Conclusion:
**Team is NOT an OCP organisational concept.** It exists only as a Paperclip implementation structure (catalog bundle of agents/projects/tasks/skills for installation). Paperclip's Team is:
- NOT a persisted database entity (no teams table)
- NOT a hierarchy node (only Agent.reportsTo exists)
- NOT a domain concept in OCP (no references anywhere in organisation package)
- An install-time configuration mechanism

**Architectural Decision: Team is only an implementation structure in Paperclip. Option B (Team as Actor subtype) and Option C (Team as separate concept) are both rejected.**

---

## H. Role vs Position/Specification Analysis

**Role already contains**:
- `name`, `description` — identity and purpose
- `responsibilities` — what the role does
- `authority_ids` — what it can do
- `constraints` — limitations
- `information_access` — what it can see
- `reports_to` — reporting relationship
- `required_capability_ids` — what capabilities it needs
- `status` — active/inactive/vacant

**A Position/Role Specification would add**:
- purpose (≈ description + responsibilities)
- required capabilities (= required_capability_ids — EXISTS)
- optional skills (NOT in Role, but referenced via CapabilityAssignment.skill_ids)
- required tools (NOT in Role, but referenced via CapabilityAssignment.tool_ids)
- responsibilities (= responsibilities — EXISTS)
- reporting relationship (= reports_to — EXISTS)
- expected outcomes (NOT in Role — but Work.outcome records outcomes for assigned work)
- team membership (NOT in Role — but Paperclip Team Catalog handles this at implementation level)

### Analysis:
Capability, Role, Assignment, and Work **already express** the relationship between organisational need and Actor assignment:
1. Role defines what capabilities are required
2. CapabilityAssignment links Actor→Capability (who has what)
3. Work is accountable to Role and assigned to Actor/Role/Person/Agent
4. Assignment links Work→assignee

Adding a Position Specification would create a generic job-description object **without evidence** that one is needed. Role already serves as the position concept per ADR-018 ("abstract position").

### Conclusion:
**No missing Position/Role Specification (Option D rejected). Role is the existing position concept.**

---

## I. Team Responsibility Semantics

In OCP, responsibility for outcomes is expressed via **Role**:
- Work is `accountable_to` a Role (ADR-034)
- Role has `responsibilities` list
- Delegation flows through `Authority` and `Delegation` between Roles

In Paperclip, responsibility is implicit via the Team Catalog:
- TEAM.md defines a manager (root agent) and includes agents
- No explicit "team responsibility" concept — it's inferred from agent hierarchy

OCP doesn't need a separate Team responsibility concept because **Role already handles accountability**. The distinction:
- **Role** = "who is accountable" (organisational concept)
- **Paperclip Team** = "how agents are bundled for installation" (implementation concept)

---

## J. People/Capability Function Analysis

### Can People/Capability be represented as an ordinary Actor/Team?

**Yes.** Evidence:

1. **Existing primitives suffice**: Role (defines the position), Actor (Person/Agent fulfills it), Capability (what they can do), CapabilityAssignment (who has what), Work (organisational need), Assignment (who does what).

2. **People/Capability as Role**: A Role named "People/Capability Lead" with responsibilities like "determine organisational capacity", "design organisational structure", "create/select Actors", "assign capabilities".

3. **People/Capability as Actor**: An Actor (Person or Agent) fulfilling the People/Capability Role. This Actor would have CapabilityAssignments for capabilities like "organisational design", "capability management", "workforce planning".

4. **Receives Work**: OCP's `assign_work` can assign Work to the People/Capability Role. E.g., Work("Analyse capacity gap for Q4 hiring").

5. **Creates Actors**: People/Capability doesn't CREATE Actors directly (by ADR-037 boundary). Instead:
   - People/Capability identifies need via Work
   - People/Capability designs structure (defines Role with required_capability_ids)
   - People/Capability provides specification to Paperclip
   - Paperclip creates Agent mapped to Role
   - Actor is created from Agent

6. **No special HR engine needed**: The flow uses existing mechanisms:
   ```
   Work → People/Capability Role
     → defines new Role (with required_capability_ids)
     → Paperclip creates Agent with that Role
     → Actor created from Agent
     → CapabilityAssignment links Actor to required Capabilities
   ```

### Answer to Q2:
**YES — People/Capability can be represented as an ordinary organisational Actor (Person or Agent fulfilling a People/Capability Role) rather than a privileged HR subsystem. No special HR engine required.**

---

## K. Chief of Staff Analysis

### Can current Actor model represent Chief of Staff?

**Yes.** Chief of Staff = a Role (e.g., "Chief of Staff") fulfilled by an Actor (Person or Agent).

### What capabilities would it require?
- "coordination" — coordinating between teams/functions
- "delegation authority" — delegating Work across roles
- "organisational oversight" — observing organisational performance
- "strategic communication" — routing strategic decisions

### Can it delegate Work?
**Yes.** Per ADR-019, Delegation records authority between Roles. Chief of Staff Role could have Authority grants to delegate to other Roles.

### Can it interact with Teams?
**Yes.** Via `Role.reports_to` — Chief of Staff Role reports to Founder/CEO Role. Other Roles report to Chief of Staff Role (authority chain).

### Can it request organisational capacity from People/Capability?
**Yes.** By assigning Work to the People/Capability Role (e.g., "Determine staffing needed for new function").

### Does it need special authority beyond ordinary organisational assignments?
**No.** ADR-031 (CEO as strategic role) and ADR-032 (COO as BAU role) already established that management is expressed through Roles, not special entities. Chief of Staff follows the same pattern.

### Constraint compliance:
- No special ChiefOfStaff class (constraint: don't create one) ✓
- Uses existing organisational primitives ✓

### Answer to Q5:
**YES — Chief of Staff can be represented as an ordinary Actor (Person or Agent) fulfilling a Chief of Staff Role with appropriate capabilities. No special Assistant architecture required.**

---

## L. C-Suite/Management Analysis

### Can architecture represent CEO → COO → CTO → teams → agents?

**Yes.** All are Roles:
- **CEO/Founder**: Role per ADR-031 (strategic only). Actor fulfills it.
- **Chief of Staff**: Role. Actor fulfills it.
- **COO**: Role per ADR-032 (BAU operational oversight). Actor fulfills it.
- **CTO/CFO/CMO**: Roles with domain responsibilities. Actor fulfills them.
- **Teams**: Paperclip implementation structures (catalog teams), or just groupings of Roles via reports_to.
- **Managers**: Roles. Actor fulfills them.
- **Specialists**: Roles. Actor fulfills them.

### What's required vs existing:
| Requirement | Existing Mechanism |
|-------------|-------------------|
| Management responsibility | Role.responsibilities, Authority |
| Reporting relationships | Role.reports_to, Agent.reportsTo (Paperclip) |
| Delegation | Delegation model (ADR-019) |
| Team ownership | Role.authority_ids; Paperclip Team Catalog |
| Capability ownership | Role.required_capability_ids |
| Work assignment | assign_work(Actor\|Role\|Person\|Agent) |

### Conclusion:
**Roles + Actors + Paperclip Teams (as implementation) ARE sufficient for C-Suite/management. No C-Suite entities needed (constraint satisfied).**

---

## M. Recursive Organisation Analysis

### Can architecture support: People/Capability → creates Roles → creates Actors → assigns Capabilities → Paperclip instantiates?

**Yes.** Evidence:

1. **People/Capability as Role**: Can be an ordinary Role with Actor fulfilling it.
2. **Receives Work**: Can receive Work to "design organisational structure".
3. **Defines new Roles**: InMemoryOrganisationControlPlane.register_role() creates new Roles.
4. **Paperclip creates Agents**: Paperclip adapter create_agent() creates Agents with specified roles and capabilities.
5. **CapabilityAssignment links Actors to Capabilities**: Existing mechanism.
6. **No privileged behaviour needed**: The same mechanisms (Work→Role→Actor→CapabilityAssignment→Paperclip) repeat at each level.

### Key insight:
The recursion is NOT in the organisational MODEL but in the PROCESS:
- Level 1: Founder (Actor) assigns Work to People/Capability Role
- Level 2: People/Capability Actor defines Role "Customer Acquisition" + required capabilities
- Level 3: Paperclip creates Agent for "Customer Acquisition" Role → Actor
- Level 4: CapabilityAssignment links new Actor to required Capabilities
- Level 5: New Actor receives Work via normal assignment

Each level uses the SAME mechanism. No special recursion logic needed.

### Answer to Q6 (partial):
**The architecture can support recursive organisation through existing Role/Capability/Work/Paperclip mechanisms. No new concepts are required for recursion.**

---

## N. Paperclip Agent/Team Capabilities

Paperclip CAN receive/construct:

| Capability | Evidence | File |
|-----------|----------|------|
| Individual Agents | `createAgentSchema`, POST /api/companies/{id}/agents | `server/src/routes/agents.ts`, `packages/shared/src/validators/agent.ts` |
| Roles/titles | Agent.role (enum: ceo, cto, etc.), Agent.title | `packages/shared/src/constants.ts:46-75`, agents schema |
| Reporting relationships | Agent.reportsTo (self-ref FK, no cycles) | `packages/db/src/schema/agents.ts:24`, `server/src/services/agents.ts:434` |
| Managers | getChainOfCommand(agentId), orgForCompany(companyId) | `server/src/services/agents.ts:1224,1201` |
| Teams/subtrees | Team Catalog (TEAM.md bundles), installCatalogTeam | `packages/teams-catalog/src/types.ts` |
| Skills | Skills catalog, company skills service | `packages/skills-catalog/src/types.ts`, `server/src/services/company-skills.ts` |
| Capabilities | Agent.capabilities (comma-separated strings) | agents schema `capabilities` field |
| Recurring work | Scheduler/heartbeat | `server/src/services/heartbeat.ts` |
| Projects | Project model (via team includes) | `packages/shared/src/validators/teams-catalog.ts` |
| Tasks | Issue model (with parentId, projectId) | `packages/db/src/schema/issues.ts` |

### Paperclip's Team Catalog configuration:
A specification like:
```yaml
# TEAM.md
name: Customer Acquisition
description: Own customer acquisition capability
schema: agentcompanies/v1
manager: agents/cmo/AGENTS.md
includes:
  - agents/demand-gen/AGENTS.md
  - agents/market-research/AGENTS.md
requiredSkills:
  - paperclipai/bundled/paperclip-operations/demand-generation
```

Paperclip installs this by creating Agents with the specified roles, linking them under the manager, and seeding skills.

---

## O. Paperclip Team Catalog/Configuration Boundary

**Key distinction**: Paperclip's Team ≠ OCP's Team.

Paperclip Team:
- Catalog entry for installation bundle
- NOT persisted as entity (no teams table)
- Defined via TEAM.md frontmatter
- Installs agents, projects, tasks, skills into a company
- Manager is a reference to an Agent (not an organisational concept)
- Structure is flat (agents list, not hierarchy tree within Team)
- No OCP semantic meaning

**Boundary**: OCP should NEVER import Paperclip's Team Catalog. Team Catalog is purely an implementation mechanism for Paperclip to bootstrap organisations. OCP expresses organisational structure via Roles, Capabilities, and Work.

---

## P. OCP → Paperclip Organisational Contract

### What OCP would send (OCP authority — what should exist):
1. **Role definitions**: id, name, description, responsibilities, required_capability_ids, reports_to
2. **Capability requirements**: which Capabilities each Role needs
3. **Work items**: what organisational effort is needed
4. **Capability gaps**: which capabilities are needed but not yet assigned

### What Paperclip receives (implementation — how it represents it):
1. **Agents**: mapped from Roles (Agent ↔ Role)
2. **Capabilities**: mapped from Agent.capabilities (comma-separated strings)
3. **Issues**: mapped from Work
4. **Assignees**: mapped from Assignment (assigneeAgentId, assigneeUserId)
5. **Reporting**: mapped from Role.reports_to → Agent.reportsTo

### Clean contract proof:
The mapping already exists in `organisation_paperclip.py`:
- `_map_agent_to_role()` maps Paperclip Agent → OCP Role
- `_map_issue_to_work()` maps Paperclip Issue → OCP Work
- `assign_work()` maps OCP assignment → Paperclip assigneeAgentId/assigneeUserId
- `create_agent()` maps OCP Role → Paperclip Agent

**A clean contract IS possible**:
```
OCP sends: [Role definitions + required_capability_ids]
Paperclip creates: [Agents with matching roles and capabilities]
```

Paperclip remains implementation; OCP defines WHAT should exist. Paperclip does NOT become the organisational authority because:
- Paperclip doesn't own capability definitions (CapabilityRegistry does)
- Paperclip doesn't own Person/Agent records (people_capability does)
- Paperclip doesn't own Work definitions (OCP does)
- Paperclip only owns operational execution state (heartbeat runs, agent runtime)

### Answer to Q4:
**YES — OCP can produce an organisational specification that Paperclip can instantiate without making Paperclip the organisational authority.**

---

## Q. Capability/Skill/Tool Ownership

| Concept | Owner | Evidence |
|---------|-------|----------|
| **Capability** | People/Capability plane | ADR-020, ADR-040. CapabilityRegistry owns lifecycle. |
| **Skill** | People/Capability plane | `skill.py` in people_capability. Has capability_id reference. |
| **Tool** | People/Capability plane | `tool.py` in people_capability. Has supports field. |
| **Role** | OCP | `role.py` in organisation package. |
| **Paperclip capabilities** | Paperclip Agent.capabilities field (comma-separated strings) | `organisation_paperclip.py:682-686` maps Agent.capabilities → Role.required_capability_ids |

### Paperclip does NOT have:
- No structured Capability model (only flat strings in Agent.capabilities)
- No SkillRegistry or ToolRegistry
- No CapabilityRegistry
- No Skill/Tool domain concepts

### Conclusion:
**Capability/Skill/Tool stay in People/Capability. No duplication in Paperclip. Paperclip's Agent.capabilities is a flat string field, not a structured capability model — it's a runtime configuration detail, not a domain concept.**

### Answer to Q2 (capability part):
**CapabilityRegistry + CapabilityAssignment are sufficient. No SkillRegistry or ToolRegistry needed. Capability definitions stay authoritative in People/Capability, referenced by Paperclip at runtime.**

---

## R. Creation Authority

| Entity | Who creates | Where | Type |
|--------|------------|-------|------|
| **Person** | People/Capability | `InMemoryAgentStore.register_person()` | Organisational decision: who should exist |
| **Agent** | People/Capability | `InMemoryAgentStore.register_agent()` | Organisational decision: who should exist |
| **Team** | Paperclip | `installCatalogTeam()` | Implementation operation: how to instantiate |
| **Role** | OCP | `InMemoryOrganisationControlPlane.register_role()` | Organisational decision: what should exist |
| **Capability** | CapabilityRegistry | `CapabilityRegistry.register()` | Organisational decision: what can be done |
| **CapabilityAssignment** | People/Capability | CapabilityAssignment records | Organisational decision: who can do what |
| **Reporting relationships** | OCP (Role.reports_to) + Paperclip (Agent.reportsTo) | Both | Shared: OCP defines intent, Paperclip persists runtime |
| **Paperclip Agent** | Paperclip API | `POST /api/companies/{id}/agents` | Implementation operation |

### Separation:
- **Organisational decision** (what should exist): OCP defines Roles, Capabilities, Work. People/Capability defines Persons, Agents, CapabilityAssignments.
- **Implementation operation** (how it's created): Paperclip creates Agents, Issues, Projects. People/Capability registers Persons, Agents.

**Paperclip is NOT the authority merely because it performs creation.** Paperclip instantiates what OCP/People/Capability decides should exist.

### Answer to Q4 (authority part):
**OCP and People/Capability hold organisational authority. Paperclip is an implementation backend that instantiates agents based on organisational decisions.**

---

## S. Minimum Required New Concepts

**ZERO new concepts required.**

Existing concepts are sufficient:
- **Role**: represents positions, responsibilities, required capabilities, reporting
- **Actor** (Person/Agent): represents acting entities
- **Capability**: represents reusable abilities
- **CapabilityAssignment**: links Actor to Capability
- **Work**: represents organisational need
- **Assignment**: links Work to assignee
- **Authority/Delegation**: represents management authority
- **Paperclip Agent**: implementation of Actor in Paperclip

The flow for "People/Capability team creates a capability-based team and Paperclip instantiates it":
1. People/Capability Actor (fulfilling People/Capability Role) receives Work to design structure
2. New Role created via `register_role()` with required_capability_ids
3. OCP sends specification to Paperclip
4. Paperclip creates Agent with that Role
5. Actor created from Agent (via InMemoryAgentStore)
6. CapabilityAssignment links Actor to required Capabilities

**No new model fields, classes, or concepts needed.**

---

## U. Alternatives Explicitly Rejected

### Option B: Team is a genuine organisational concept and should become an Actor subtype
**REJECTED.** Paperclip's Team is a catalog/install structure, not a domain entity. No Team concept exists in OCP. No OCP model references Team. ActorType enum only has PERSON and AGENT. Adding Team as Actor subtype would create a concept with no OCP evidence.

### Option C: Team is a genuine organisational concept but should remain separate from Actor
**REJECTED.** Same reasoning as Option B. Paperclip's Team is an implementation detail; OCP has no need for it as a domain concept.

### Option D: A Role/Position Specification is the missing organisational concept
**REJECTED.** Role already has: name, description, responsibilities, authority_ids, constraints, information_access, reports_to, required_capability_ids, status. Adding Position Specification would create a generic job-description object without evidence.

### Special ChiefOfStaff class
**REJECTED by constraint.** Chief of Staff is a Role, not a special class.

### Special HR engine
**REJECTED by constraint.** People/Capability is an ordinary organisational function.

### C-Suite entities
**REJECTED by constraint.** CEO/COO/CTO are Roles (ADR-031, ADR-032).

### SkillRegistry/ToolRegistry
**REJECTED by constraint.** CapabilityRegistry exists and is sufficient.

### Paperclip as organisational authority
**REJECTED by constraint.** Paperclip is implementation backend.

### Dynamic team generation
**REJECTED by constraint.** Not in scope.

### Paperclip team provisioning
**REJECTED by constraint.** Not in scope.

### Generic event sourcing/RAG/knowledge graph
**REJECTED by constraint.** Not in scope.

---

## V. Recommended Next Increment

All investigation is complete. Architectural Decision: **A** (minimum coherent model) — existing Actor/Role/Capability/Assignment primitives are sufficient; Team is only an implementation structure.

Potential next increments:
1. **Implement People/Capability function as a Role with Work**: Create People/Capability Role, assign capacity-planning Work, define capability gap detection flow
2. **Build OCP→Paperclip organisational specification contract**: Formalise the contract for sending Role definitions + capability requirements to Paperclip for agent instantiation
3. **Implement Chief of Staff as a Role**: Create Chief of Staff Role with delegation authority, test the coordination flow
4. **Investigate capability gap detection**: How does the organisation discover it needs a new capability and trigger People/Capability response?

---

## Final Questions

### Q1: "Can Team legitimately be an Actor in the OCP model?"

**No.** Team exists only as a Paperclip catalog/install structure (`@paperclipai/teams-catalog`). It has no presence in the OCP domain model. Paperclip's Team is NOT a persisted database entity (no teams table), NOT a hierarchy node (only Agent.reportsTo exists), and NOT referenced by any OCP code. The OCP has no mechanism to assign Work to, delegate authority to, or assign Capabilities to a Team. Role already serves as the organisational accountability unit (Work.accountable_role_id). Paperclip's Team is an implementation structure for bundling agents during installation — it should NOT become an Actor in OCP.

### Q2: "Can a People/Capability function be represented as an ordinary organisational Actor/Team rather than a privileged HR subsystem?"

**Yes.** People/Capability can be represented as:
- A **Role** (e.g., "People/Capability Lead") with responsibilities for organisational design, capability management, workforce planning
- An **Actor** (Person or Agent) fulfilling that Role
- CapabilityAssignments linking that Actor to capabilities like "organisational design"
- A Work recipient (receives Work to analyse capacity gaps, design structure)

The entire flow uses existing mechanisms: Work → Role → Actor → CapabilityAssignment → Paperclip Agent creation. No special HR engine, no privileged subsystem. People/Capability is an ordinary organisational function that happens to create other organisational structures — but it does so through the same Role/Capability/Work mechanisms as every other function.

### Q3: "Is there a missing Role/Position Specification between organisational capability requirements and Actor assignment?"

**No.** Role already serves this purpose:
- `name`, `description` — identity and purpose
- `responsibilities` — what the role does
- `required_capability_ids` — what capabilities it requires
- `authority_ids` — what it can do
- `constraints` — limitations
- `information_access` — what it can see
- `reports_to` — reporting relationship
- `status` — active/inactive/vacant

CapabilityAssignment links Actor→Capability (who has what). Work is accountable to Role and assigned to Actor/Role/Person/Agent. Assignment links Work→assignee. The chain from organisational need to Actor assignment is: Need (Work) → accountable Role (required_capability_ids) → Actor fulfilling Role → CapabilityAssignment (authorisation to exercise Capability). No Position Specification is needed.

### Q4: "Can OCP produce an organisational specification that Paperclip can instantiate without making Paperclip the organisational authority?"

**Yes.** The mapping already exists in `organisation_paperclip.py`:
- OCP Role → Paperclip Agent (via _map_agent_to_role, create_agent)
- OCP Work → Paperclip Issue (via _map_issue_to_work, create_work)
- OCP Assignment → Paperclip assigneeAgentId/assigneeUserId (via assign_work)
- OCP Role.reports_to → Paperclip Agent.reportsTo (via _map_agent_to_role)

OCP sends WHAT should exist (Role definitions + required_capability_ids). Paperclip instantiates HOW it represents them (Agents with roles and capabilities). Paperclip remains an implementation backend because:
- It doesn't own capability definitions (CapabilityRegistry does)
- It doesn't own Person/Agent records (people_capability does)
- It doesn't own Work definitions (OCP does)
- It only owns operational execution state

### Q5: "Can the Chief of Staff be represented as an ordinary Actor with appropriate capabilities rather than a special Assistant architecture?"

**Yes.** Chief of Staff = a Role (e.g., "Chief of Staff") with responsibilities for coordination, delegation, oversight. An Actor (Person or Agent) fulfills this Role with CapabilityAssignments for "coordination", "delegation authority", "organisational oversight". It delegates Work via existing Delegation mechanism (ADR-019). It interacts with Teams via Role.reports_to hierarchy. It requests capacity from People/Capability via Work assignment. ADR-031 (CEO as strategic role) and ADR-032 (COO as BAU role) already established that management is expressed through Roles, not special entities. Chief of Staff follows the same pattern.

### Q6: "What is the smallest set of concepts we actually need to add before we can have a People/Capability team create a capability-based team and have Paperclip instantiate it?"

**None.** The existing concepts are sufficient:
- **Role** defines what should exist (with required_capability_ids)
- **Actor** (Person/Agent) fulfills the Role
- **Capability** defines what can be done
- **CapabilityAssignment** links Actor to Capability
- **Work** represents organisational need
- **Assignment** links Work to assignee
- **Paperclip Agent** is the implementation of Actor in Paperclip

The flow:
1. People/Capability Actor receives Work to design structure
2. New Role created with required_capability_ids
3. OCP sends Role specification to Paperclip (existing adapter)
4. Paperclip creates Agent mapped to Role
5. Actor created from Agent
6. CapabilityAssignment links Actor to required Capabilities

The one operational gap — OCP doesn't create Actors directly — is BY DESIGN (ADR-037), not a conceptual gap. People/Capability owns Actor creation; OCP defines what they should do.

---

## Architectural Decision: **A** (minimum coherent model)

Existing Actor/Role/Capability/Assignment primitives are sufficient. Team is only a Paperclip implementation structure. No new concepts required.

Supporting decisions:
- **E**: People/Capability can be represented as ordinary Actor/Team
- **A**: Team is only an implementation structure in Paperclip

Both decisions A and E are required for the minimum coherent model (Option F, but minimum).

---

## T. Architectural Tests Added

38 tests in `packages/organisation/tests/test_increment40_organisation_team_role_boundary.py`:

### A. Actor Model Facts (5 tests)
1. `test_actor_type_enum_has_only_person_and_agent` — ActorType has PERSON and AGENT only
2. `test_actor_has_no_team_subtype` — No Team in ActorType
3. `test_actor_links_to_person_or_agent_via_reference_id` — Actor.reference_id pattern
4. `test_actor_is_lightweight_reference_not_entity` — Actor has no lifecycle fields
5. `test_organisation_does_not_define_actor` — Actor not in organisation package (ADR-037)

### B. Role Model Facts (5 tests)
6. `test_role_is_abstract_position_not_person_or_agent` — Role is not Person/Agent
7. `test_role_has_required_capability_ids` — Role declares capabilities
8. `test_role_has_responsibilities_authority_constraints` — Role has organisational semantics
9. `test_role_has_reports_to_for_hierarchy` — Role has reporting relationship
10. `test_role_status_has_vacant` — Role can be vacant (position unfilled)

### C. Work Accountability Facts (4 tests)
11. `test_work_accountable_to_role` — Work.accountable_role_id exists
12. `test_work_has_multiple_assignee_fields` — role_id, actor_id, person_id, agent_id
13. `test_assign_work_accepts_actor_role_person_agent` — assign_work signature
14. `test_work_has_no_team_assignee` — No team_id on Work

### D. Capability Model Facts (3 tests)
15. `test_capability_has_tool_and_skill_kinds` — CapabilityKind enum
16. `test_capability_distinct_from_skill_and_tool` — Capability ≠ Skill ≠ Tool
17. `test_capability_owned_by_people_capability` — Capability in people_capability package

### E. Assignment Model Facts (3 tests)
18. `test_capability_assignment_links_actor_to_capability` — actor_id + capability_id
19. `test_capability_assignment_has_skill_tool_references` — skill_ids, tool_ids
20. `test_org_assignment_links_work_to_assignee` — Assignment model

### F. Team Concept Facts (5 tests)
21. `test_no_team_in_organisation_package` — No Team model in OCP
22. `test_paperclip_team_is_catalog_not_entity` — No teams DB table
23. `test_actor_type_enum_cannot_be_team` — Team not addable to ActorType without change
24. `test_assign_work_does_not_accept_team` — No Team parameter
25. `test_no_team_hierarchy_concept` — No containment model

### G. People/Capability Representation (4 tests)
26. `test_people_capability_can_be_represented_as_role` — Role exists for it
27. `test_capability_assignment_can_link_person_to_capacity_capability` — CapabilityAssignment mechanism
28. `test_assign_work_can_target_people_capability_role` — Work assignment to any Role
29. `test_no_hr_engine_exists` — No HR-specific engine

### H. Chief of Staff Representation (3 tests)
30. `test_chief_of_staff_can_be_role` — No special class needed
31. `test_chief_of_staff_uses_existing_delegation` — Delegation mechanism (ADR-019)
32. `test_chief_of_staff_no_special_authority_required` — Ordinary organisational authority

### I. C-Suite Representation (2 tests)
33. `test_ceo_is_role_not_entity` — ADR-031
34. `test_coo_is_role_not_entity` — ADR-032

### J. Recursive Organisation (3 tests)
35. `test_people_capability_can_create_roles` — register_role exists
36. `test_paperclip_can_create_agents_from_roles` — create_agent maps Role→Agent
37. `test_capability_assignment_links_new_actor_to_capabilities` — Assignment mechanism
38. `test_recursive_flow_uses_same_mechanisms_each_level` — No privileged recursion needed

### K. Paperclip Contract (2 tests)
39. `test_organisation_paperclip_maps_role_to_agent` — Role→Agent mapping
40. `test_organisation_paperclip_maps_work_to_issue` — Work→Issue mapping

### L. Authority Facts (2 tests)
41. `test_organisations_decide_what_should_exist` — OCP creates Roles, Work
42. `test_paperclip_implements_how_agents_are_created` — Paperclip API call

---

## U. Alternatives Rejected (in tests)

43. `test_team_as_actor_subtype_is_rejected` — No evidence
44. `test_position_specification_is_rejected` — Role suffices
45. `test_special_chief_of_staff_class_rejected` — Role suffices
46. `test_paperclip_as_authority_rejected` — OCP defines what exists

---

## V. Remaining Gaps

None — all 13 investigation areas resolved with Decision A.

---

## Final Summary

**Architectural Decision: A** (minimum coherent model) — existing Actor/Role/Capability/Assignment primitives are sufficient; Team is only a Paperclip implementation structure. Supporting decision **E** — People/Capability can be represented as ordinary Actor/Team.

**Key findings**:
- Team is a Paperclip catalog/install structure, not an OCP domain concept
- Role already serves as position/accountability unit
- No Position Specification needed
- People/Capability is ordinary organisational function (Role + Actor + Work + CapabilityAssignment)
- Chief of Staff is a Role, not a special class
- C-Suite is Roles, not entities
- Recursive organisation uses same mechanisms at each level
- Clean OCP→Paperclip contract exists via existing adapter
- Capability/Skill/Tool ownership in People/Capability
- Creation authority: OCP/People/Capability decide, Paperclip instantiates

**Zero production changes required.**
