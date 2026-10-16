# ADR-034: Work Accountability Model

Status: Accepted

Decision

Work is accountable to an appropriate Role, not owned by Organisation/Control. Work carries explicit accountability, coordination, assignment, and outcome fields. The OrganisationControlPlane provides mechanisms for work coordination but does not itself own or coordinate work.

Context

The previous model treated Organisation/Control as the owner of all Work. This investigation revealed that Work needs explicit accountability relationships, and that different types of work (BAU vs project) have different accountability structures.

Work Model

Work contains:
- `id`: unique identifier
- `title`: descriptive title
- `description`: detailed description
- `work_type`: "bau" | "project" | "initiative"
- `status`: pending | assigned | in_progress | completed | cancelled | escalated
- `priority`: normal | high | critical
- `accountable_role_id`: Role accountable for the outcome
- `coordinating_role_id`: Role coordinating the work (may be same as accountable)
- `requested_by_role_id`: Role that requested the work
- `assignee_role_id`: Role assigned to perform the work
- `assignee_person_id`: Person assigned (if specific individual)
- `assignee_agent_id`: Agent assigned (if specific runtime entity)
- `required_capability_ids`: list of Capability IDs required
- `acceptance_criteria`: list of outcome criteria
- `dependencies`: list of Work IDs this work depends on
- `deliverables`: list of expected deliverables
- `outcome`: dict storing the actual outcome when completed
- `constraints`: list of constraints
- `context`: additional context dict
- `created_at`, `updated_at`: timestamps
- `metadata`: additional metadata

Accountability Rules

1. Every Work item has exactly one `accountable_role_id`.
2. `accountable_role_id` is never null.
3. `coordinating_role_id` may be null (for simple work where the accountable role also coordinates).
4. `assignee_role_id` may be null (for work not yet assigned).
5. `assignee_person_id` and `assignee_agent_id` are optional specific assignees.

BAU vs Project Work

| Aspect | BAU Work | Project Work |
|---|---|---|
| work_type | "bau" | "project" or "initiative" |
| accountable_role | COO or functional manager | C-Suite executive |
| coordinating_role | Functional manager | Project Manager |
| assignee_role | Operational role | Specialist role |
| duration | ongoing | bounded |
| outcome | operational performance | business outcome |

OrganisationControlPlane Responsibility

OrganisationControlPlane:
- Stores Work records
- Provides role lookup for accountability
- Enables work assignment
- Provides organisational context
- Does NOT coordinate work
- Does NOT become the project manager or COO
- Does NOT execute work

Rationale

1. Explicit accountability prevents work from becoming orphaned or ambiguously owned.
2. Separating accountable, coordinating, and assigned roles enables distributed coordination.
3. BAU and project work have different management needs; the model must express both.
4. OrganisationControlPlane as mechanism, not coordinator, preserves the boundary between organisational infrastructure and management.

Consequences

- Work model gains multiple role fields (accountable, coordinating, requested_by, assignee).
- OrganisationControlPlane does not grow coordination logic.
- CEO does not own Work coordination.
- Future implementations can query Work by accountability chain.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-027: Work-Capability "Requires" Relationship
- ADR-031: CEO as Strategic Role
- ADR-032: COO as Role for BAU
- ADR-033: Project Management as Role
- ADR-036: Distributed Organisational Coordination
