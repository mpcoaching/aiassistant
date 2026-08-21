# ADR-016: CapabilityRequest as Governance Artifact

Status: Proposed

Decision

`CapabilityRequest` is a transient governance object, not an enduring enterprise asset. Once approved, it is persisted as an `EnterpriseConcept` (`kind=capability`, `status=draft`). The governance decision is durable in the EnterpriseConcept payload and provenance.

Context

The system needs a mechanism to request new capabilities. However, not every request for a capability is enduring enterprise knowledge. A CapabilityRequest is a governance artifact — it exists to manage the approval flow, not to represent knowledge.

The EnterpriseConcept model already provides:
- Persistent storage via ConceptStore
- Status lifecycle (draft → active → deprecated)
- Provenance tracking
- Payload for arbitrary structured data

CapabilityRequest should leverage these existing mechanisms rather than creating a new persistence subsystem.

Decision

1. CapabilityRequest is a Pydantic model used during the approval flow.
2. When approved, the CapabilityRequest is promoted to an EnterpriseConcept:
   - kind = capability
   - status = draft (not yet implemented)
   - payload includes the original request, governance history, and later the compiled_ref
   - provenance includes source_session_id and recognition_level
3. The CapabilityRequest Pydantic object is transient. It is not stored in ConceptStore directly.
4. Once the capability is implemented and registered, the EnterpriseConcept status moves to active.

Lifecycle

  CapabilityRequest (transient)
      status: pending
          ↓
      [human approves]
          ↓
      EnterpriseConcept created:
          kind=capability
          status=draft
          payload = {
              capability_request: { name, purpose, inputs, outputs, acceptance_criteria },
              governance: { approved_by, approved_at, rationale }
          }
          ↓
      [Kilo implements]
          ↓
      compiled_ref added
          tests_passed = true
          ↓
      status = active
          ↓
      [invoked, matured]
          ↓
      maturation_history updated

Rationale

1. A request is not enduring knowledge — the resulting capability IS an enterprise asset.
2. The request is the governance trail, not the asset itself.
3. Reusing EnterpriseConcept avoids creating a parallel persistence subsystem.
4. The status field (draft → active → deprecated) maps cleanly to the capability lifecycle.

Consequences

- CapabilityRequest is not directly queryable from ConceptStore.
- Approved requests ARE queryable as EnterpriseConcepts with kind=capability.
- Governance history is preserved even after the transient CapabilityRequest object is discarded.
- The system can answer "what capabilities have been requested/approved?" via ConceptStore queries.

Related

- ADR-014: Capability-First Routing
- ADR-015: Human-as-Approval-Layer for Capability Specifications
