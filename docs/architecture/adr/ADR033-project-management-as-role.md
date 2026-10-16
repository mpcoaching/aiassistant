# ADR-033: Project Management as Organisational Role

Status: Accepted

Decision

Project Manager / Delivery Manager is an organisational ROLE, not an operations engine. The PM coordinates project delivery, sequences work, tracks progress, manages dependencies, surfaces risks, and coordinates specialist roles. The PM does NOT become the Operations plane, execute every task, own every capability, or replace specialist roles.

Context

Strategic initiatives require dedicated coordination beyond BAU management. The PM role provides that coordination while preserving the distinction between management/coordination and operational execution.

Project / Strategic Initiative Flow

    CEO
      ↓
  strategic decision
      ↓
  accountable C-Suite executive
      ↓
  Project Manager / Delivery Manager
      ↓
  specialist roles
      ↓
  Operations

PM Responsibilities

- Coordinate project work
- Sequence work activities
- Track progress against plan
- Manage dependencies between work items
- Surface risks and issues
- Coordinate specialist roles
- Report outcomes to accountable executive
- Escalate issues appropriately

PM Explicitly Does NOT

- Become the Operations plane
- Execute every task
- Own every capability
- Replace specialist roles
- Become CEO
- Own the business outcome (that belongs to the accountable C-Suite executive)

Accountability Distinction

- **Accountable C-Suite executive** owns the business outcome
- **Project Manager** is accountable for delivery coordination
- **Specialist roles** own their respective work products
- **Operations** executes operational activity

Rationale

1. Project coordination is a management function, not an execution function.
2. The PM role enables distributed coordination without centralising all control.
3. Separating PM from Operations preserves the four-plane architecture.
4. The accountable C-Suite executive remains answerable for outcomes, not the PM.

Consequences

- A new Role type "ProjectManager" is available in the organisational model.
- Work created for strategic initiatives is accountable to the PM for coordination, and to the C-Suite executive for business outcome.
- OrganisationControlPlane provides role definitions and assignment mechanisms; it does not coordinate the project.
- Specialist roles retain authority over their work products.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-028: Role Workflow Handoff Model
- ADR-031: CEO as Strategic Role
- ADR-034: Work Accountability Model
- ADR-036: Distributed Organisational Coordination
