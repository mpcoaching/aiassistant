# ADR-032: COO as Organisational Role for BAU

Status: Accepted

Decision

The COO is an organisational ROLE accountable for Business-as-Usual (BAU) operational performance. The COO observes operational outcomes, manages operational capacity, handles exceptions, and coordinates functional managers. The COO does NOT become the Operations plane, micro-manage every task, or execute operational work.

Context

BAU work and strategic project work follow different coordination paths. BAU requires continuous operational oversight by a management role, not by the CEO or by the OrganisationControlPlane itself. The COO provides that oversight.

BAU Flow

    CEO
      ↓
  strategic direction
      ↓
      COO
      ↓
  functional/business managers
      ↓
  operational roles
      ↓
  Operations

COO Responsibilities

- Operational performance oversight
- BAU outcomes tracking
- Operational capacity management
- Significant exception handling
- Cross-functional operational coordination
- Reporting operational health to CEO

COO Explicitly Does NOT

- Micro-manage every operational task
- Execute operational work
- Become the Operations plane
- Own capability lifecycle
- Own EIMS
- Replace functional managers

OrganisationControlPlane enables the COO to observe and manage operational performance without itself becoming the COO.

Rationale

1. BAU requires dedicated management oversight separate from strategic decision-making.
2. The COO role prevents the CEO from being drawn into operational details.
3. Functional managers retain authority within their domains; the COO coordinates across functions.
4. Operations remains the execution plane; the COO observes and manages at the appropriate level.

Consequences

- A new Role type "COO" is available in the organisational model.
- Work flowing through BAU channels is accountable to the COO or delegated functional managers.
- OrganisationControlPlane provides reporting relationships and organisational context for the COO.
- Operations plane continues to execute workflows without COO intervention.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-028: Role Workflow Handoff Model
- ADR-034: Work Accountability Model
- ADR-036: Distributed Organisational Coordination
