# ADR-024: CEO as Organisational Role, not Universal Router

Status: Accepted

Decision

CEO is an organisational ROLE, not the central AI agent. CEOAgent consumes OrganisationControlPlane via dependency injection and uses it for role lookup, work assignment, and authority checks. CEO does not discover or select capabilities.

Context

The current CEO implementation routes all requests through capability matching and execution. This makes CEO the universal router and collapses the organisational boundary. The correct flow is: request -> enterprise context -> organisational context -> CEO role judgement -> organisational decision -> work/delegation/escalation -> appropriate role -> operations when required.

Decision

1. CEO responsibilities:
   - Receives organisational context
   - Interprets enterprise strategy
   - Establishes/coordinates priorities
   - Allocates work
   - Delegates responsibility
   - Coordinates organisational roles
   - Identifies organisational gaps
   - Identifies capability gaps
   - Reviews outcomes
   - Escalates when necessary

2. CEO does NOT:
   - Execute operational tasks
   - Directly orchestrate runtime agents
   - Discover/select capabilities
   - Own capability lifecycle
   - Own EIMS
   - Become the universal request router
   - Replace the OrganisationControlPlane
   - Become the system's central AI agent

3. CEOAgent receives OrganisationControlPlane via DI. The orchestrate() method routes through self._org.get_organisational_context(request) and uses org-plane methods only.

4. _match_capabilities() is removed entirely from CEOAgent. Direct CapabilityRegistry instantiation for matching is removed. Direct capability selection/execution logic is removed.

5. CEO may identify that a capability gap exists (as an organisational observation) but does not search CapabilityRegistry or select capabilities.

Rationale

1. The CEO is a role in the organisation, not the system's central orchestrator.
2. Separating CEO from capability matching preserves the three-plane architecture.
3. Dependency injection makes the boundary explicit and testable.

Consequences

- CEO tests verify absence of capability matching logic.
- Architectural boundary tests guard against CEO imports of capability modules.
- CEO orchestrate() returns dict[str, Any] for backward-compatible shape but routes through org plane.

Related

- ADR-017: Three-Plane Architecture
- ADR-020: Capability Ownership by People/Capability
- ADR-022: OrganisationControlPlane Abstraction
