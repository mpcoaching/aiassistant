# ADR-036: Distributed Organisational Coordination

Status: Accepted

Decision

Organisational coordination is distributed according to responsibility and authority. No single role, service, or plane coordinates all organisational activity. The OrganisationControlPlane provides mechanisms and context; actual coordination belongs to appropriate roles (CEO, COO, C-Suite executives, Project Managers, functional managers, specialist roles).

Context

The previous model risked making OrganisationControlPlane the universal coordinator. This investigation confirmed that coordination must be distributed: each role coordinates only within the authority and accountability appropriate to that role.

Coordination Model

```
Enterprise
   ↓
strategic intent
   ↓
CEO
   ↓
strategic decision
   ↓
accountable executive / management
   ↓
management / project coordination
   ↓
organisational roles
   ↓
operations
   ↓
outcomes
   ↓
enterprise learning
```

Role Coordination Responsibilities

| Role | Coordinates | Does NOT |
|---|---|---|
| CEO | Strategic direction, major interventions | Day-to-day work, project delivery, operational tasks |
| COO | BAU operational performance, cross-functional coordination | Strategic decisions, project delivery, execution |
| C-Suite executive | Business outcome accountability for initiatives | Project coordination details, specialist work |
| Project Manager | Project delivery coordination, dependencies, risks | Business outcomes, strategic decisions, execution |
| Functional manager | Functional responsibility, team performance | Cross-functional strategy, project delivery |
| Specialist role (EA, SA, BA, Dev, QA) | Specialist work products, quality | Project coordination, business outcomes |
| Operations | Workflow execution, runtime, tools | Strategic decisions, role accountability |

OrganisationControlPlane Responsibility

OrganisationControlPlane:
- Provides role definitions and relationships
- Provides reporting hierarchy
- Provides authority and delegation records
- Provides organisational context for requests
- Enables work assignment through Assignment records
- Does NOT coordinate work
- Does NOT become the project manager or COO
- Does NOT execute work
- Does NOT make strategic decisions

Rationale

1. Distributed coordination prevents God services.
2. Each role has clear accountability boundaries.
3. The OrganisationControlPlane as mechanism, not brain, preserves the separation between organisational infrastructure and management.
4. Real organisations coordinate through roles, not through central orchestrators.

Consequences

- Future CEO implementation makes strategic pronouncements, not work assignments.
- Future COO implementation observes BAU performance, manages exceptions.
- Future PM implementation coordinates project delivery.
- OrganisationControlPlane API remains narrow; coordination logic lives in role-specific services (future).
- Tests verify that no plane or role exceeds its coordination boundary.

Related

- ADR-017: Three-Plane Architecture
- ADR-022: OrganisationControlPlane Abstraction
- ADR-031: CEO as Strategic Role
- ADR-032: COO as Role for BAU
- ADR-033: Project Management as Role
- ADR-034: Work Accountability Model
