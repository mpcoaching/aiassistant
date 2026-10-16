# ADR-015: Human-as-Approval-Layer for Capability Specifications

Status: Proposed

Decision

New capabilities require explicit human approval of their specification before implementation. Specification approval and implementation approval are separate governance decisions.

Context

The system must be able to identify gaps in its capability set and request new capabilities. However, autonomous capability creation is not the goal of the first experiment. The human fulfils the "IT function" role initially.

The architecture distinguishes between:
- WHAT to build (specification approval)
- HOW to build it (implementation approval)
- WHETHER to deploy it (deployment approval)

For the first slice, we prove the first two. The third is deferred until capabilities have side effects beyond ConceptStore records.

Decision

1. When no capability matches a request, the system produces a CapabilityRequest template.
2. The human fills the template (inputs, outputs, acceptance criteria).
3. The human approves the specification.
4. The approved specification becomes an implementation task for Kilo.
5. Kilo implements, tests, and registers the capability.
6. The capability is then available for execution.

Approval of a specification is NOT approval of an implementation. The human approves WHAT to build. Kilo proposes HOW. The human reviews the implementation before it is registered.

Rationale

1. We are proving the architecture before automating it.
2. The human provides the "capability architect" function until the system can do it reliably.
3. Separate specification and implementation approvals create a clear governance boundary.
4. This matches the existing governance model where human_approval is a PatternStep gate.

Consequences

- CapabilityRequest gains a governance lifecycle: pending → approved → rejected → implemented.
- Approved CapabilityRequests are persisted as EnterpriseConcepts with status=draft.
- Governance history (approved_by, approved_at, rationale) is preserved in the EnterpriseConcept payload and provenance.
- The system does not autonomously implement capabilities in the first slice.

Related

- ADR-014: Capability-First Routing
- ADR-016: CapabilityRequest as Governance Artifact
