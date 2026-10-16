# ADR-031: CEO as Strategic Role, Not Orchestrator

Status: Accepted

Supersedes: ADR-024

Decision

The CEO is an organisational ROLE with strategic responsibilities only. The CEO makes strategic decisions, establishes strategic direction, observes organisational performance, and intervenes at the strategic level. The CEO does NOT organise day-to-day work, assign individual operational tasks, manage project delivery, coordinate specialist work, select capabilities, execute operational work, or act as a universal system router.

Context

ADR-024 correctly identified CEO as an organisational role, not a central AI agent. However, it still assigned CEO orchestration-like responsibilities (allocates work, delegates responsibility, coordinates organisational roles). This increment's investigation revealed that these responsibilities belong to other roles (COO, C-Suite executives, Project Managers, functional managers), not to the CEO.

The CEO is accountable for the organisation at the strategic level, but is not the mechanism through which all work is coordinated.

CEO Strategic Responsibilities

- Interprets enterprise information and strategy
- Makes strategic decisions
- Establishes strategic direction
- Makes strategic pronouncements
- Observes organisational performance and outcomes
- Reviews significant outcomes
- Intervenes when necessary at strategic level
- Changes strategic direction when necessary
- Escalates or resolves matters within CEO authority

CEO Explicitly Does NOT

- Organise day-to-day work
- Assign individual operational tasks
- Determine who does every piece of work
- Manage project delivery
- Coordinate specialist work
- Select capabilities for individual work
- Execute operational work
- Orchestrate agents
- Become the universal system router

CEO Decision Flow

    Enterprise context
        ↓
      CEO
        ↓
  strategic decision
        ↓
  "We should do X."
        ↓
  Hand to accountable executive / management structure

The CEO decides WHAT should be done at the strategic level. The organisational management structure determines HOW and WHO.

Rationale

1. A CEO who orchestrates everything becomes a God service.
2. Strategic decision-making is distinct from operational coordination.
3. Real organisations separate strategic leadership from management execution.
4. Modelling the CEO as strategic-only preserves the boundary between Enterprise and Organisation/Control planes.

Consequences

- CEOAgent no longer allocates work or assigns tasks.
- CEOAgent makes strategic pronouncements and delegates to accountable roles.
- OrganisationControlPlane does not treat CEO as the work allocator.
- Future C-Suite roles (COO, CIO, etc.) own operational and functional coordination.
- Project Manager role owns project delivery coordination.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-032: COO as Role for BAU
- ADR-033: Project Management as Role
- ADR-034: Work Accountability Model
- ADR-036: Distributed Organisational Coordination
