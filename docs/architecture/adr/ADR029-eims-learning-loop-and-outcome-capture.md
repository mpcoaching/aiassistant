# ADR-029: EIMS Learning Loop and Outcome Capture

Status: Accepted

Decision

Operational execution outcomes flow back into the organisation through a structured learning loop that creates durable EnterpriseConcepts in EIMS. Not all operational state becomes durable knowledge. The boundary between transient operational state and durable enterprise knowledge is explicit.

Context

The Increment 7 investigation revealed that execution results, operational outcomes, and learning must be captured systematically. Without a clear boundary, EIMS risks becoming a task manager, workflow engine, or agent controller — all prohibited by existing architecture.

Decision

1. What becomes durable EIMS knowledge:
   - Strategy decisions and rationale
   - Capability definitions and maturation history
   - Work outcomes (success, failure, lessons learned)
   - Enterprise assets produced by roles (requirements, designs, implementations, verification results)
   - Governance decisions (approved CapabilityRequests)
   - Institutional learning (patterns, playbooks, policies)

2. What remains transient operational state:
   - Session state (running context, step outputs, human responses)
   - Workflow execution state (current step, intermediate results)
   - Runtime agent state (in-flight tool calls, temporary buffers)
   - Human-in-the-loop pending state (awaiting input)

3. Learning loop flow:

    operational execution
          |
          | produces
          v
    execution result
          |
          | evaluated by
          v
    outcome assessment
          |
          | creates/updates
          v
    EnterpriseConcept (EIMS)
          |
          | informs
          v
    future organisational decisions

4. Outcome assessment is an operational concern that decides what to promote to EIMS. Not every execution needs to create an EnterpriseConcept.

5. Capability maturation is one specific learning loop:
   - execute_capability() returns ExecutionResult
   - caller invokes CapabilityRegistry.record_invocation(id, outcome)
   - MaturationHistory is updated in the EnterpriseConcept payload
   - When thresholds are met, promotion to COMPILED mode may occur

6. The CEO consults EIMS for previous solutions and organisational context but does not write to EIMS directly. EIMS writes happen through:
   - People/Capability (capability maturation)
   - Operations (outcome capture)
   - Organisation/Control (work outcomes)

Rationale

1. Durable enterprise knowledge outlives any single agent, session, or workflow.
2. Separating transient state from durable knowledge prevents EIMS from becoming a runtime database.
3. Explicit learning loops make institutional learning observable and governable.
4. Outcome assessment as an operational concern keeps EIMS focused on storage, not evaluation logic.

Consequences

- EIMS (ConceptStore) is write-accessible by multiple planes but owned by the Enterprise plane.
- A future OutcomeRecorder or LearningService may formalise the outcome->EIMS promotion logic.
- Capability maturation is the first implemented learning loop; work outcome learning is future work.
- CEO uses ConceptStore for EIMS reads (previous solutions, strategy context).

Related

- ADR-021: EIMS Boundary and ConceptStore as Current Implementation
- ADR-017: Three-Plane Architecture
- ADR-026: People/Capability as Peer Domain Plane
