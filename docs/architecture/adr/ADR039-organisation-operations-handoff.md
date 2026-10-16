# ADR-039: Organisation → Operations Handoff via Work State

Status: Accepted

Decision

The organisational → operational handoff occurs through Work state transition, not through OrganisationControlPlane execution. Organisation/Control marks Work as ready (`mark_work_ready()` → `WorkStatus.IN_PROGRESS`). Operations discovers/accepts Work and executes it via its own entry points (`PathwayRuntime.invoke()`, `execute_workflow()`). Execution results flow back to Organisation for outcome assessment.

Context

Increment 10 introduced `OrganisationControlPlane.execute_work()` as the handoff seam. Increment 11 investigation revealed this was a boundary violation: OCP imported `PathwayRuntime`, created `PathwayCallRequest`, invoked operational execution, and returned operational results. This made OCP an execution facade.

The corrected model separates handoff from execution.

Decision

1. **Organisation/Control plane:**
   - Creates Work
   - Assigns Work (`assign_work()`)
   - Marks Work ready (`mark_work_ready()` → status transition to `IN_PROGRESS`)
   - Does NOT execute Work
   - Does NOT import `PathwayRuntime`, `Session`, `execute_workflow()`, or any operational runtime
   - Does NOT invoke capabilities, tools, or agents

2. **Operations plane:**
   - Discovers/accepts Work ready for execution
   - Executes Work via its own entry points:
     - `PathwayRuntime.invoke()` — pattern execution
     - `execute_workflow()` — workflow execution
     - `PatternRuntime.invoke_step()` — capability execution
   - Returns execution result (evidence) to Organisation
   - Does NOT determine organisational authority
   - Does NOT assign organisational accountability
   - Does NOT decide strategic or organisational priorities

3. **The handoff is implicit through Work state:**
   - `ASSIGNED` → `IN_PROGRESS`: organisational handoff signal
   - Operations observes Work.status and executes
   - No event bus, queue, or explicit handoff call required

4. **Execution result is evidence, not automatic organisational acceptance:**
   - Operations returns execution result
   - Organisation assesses result against `acceptance_criteria`
   - Organisation updates `Work.outcome` and `Work.status`
   - Organisation decides: accept, reject, escalate, reassign

5. **Capability requirements remain organisational/People-Capability concerns:**
   - `Work.required_capability_ids` declares what is required
   - Operations must NOT interpret this as permission to discover/select capabilities
   - Capability discovery, matching, and lifecycle remain in People/Capability

Rationale

1. A handoff mechanism is legitimate; an execution mechanism on OCP is not.
2. The smallest abstraction that proves the boundary is a Work status transition.
3. Operations already has sufficient entry points; no new execution abstraction is needed.
4. Implicit handoff through state avoids premature event/queue infrastructure.
5. This preserves the four-plane separation established in Increments 6-9.

Consequences

- `OrganisationControlPlane` no longer imports or depends on `PathwayRuntime` or any operational substrate.
- `mark_work_ready()` is the sole organisational handoff mechanism.
- Operations consumers (AssistantChatService, workflow runner, future PM services) are responsible for discovering and executing ready Work.
- Future event/queue infrastructure can be added without changing the domain model.
- Paperclip maps to OCP mechanisms only, not to operational execution.

Related

- ADR-017: Three-Plane Architecture
- ADR-022: OrganisationControlPlane Abstraction
- ADR-031: CEO as Strategic Role
- ADR-034: Work Accountability Model
- ADR-036: Distributed Organisational Coordination
- ADR-037: Person/Agent Ownership by People/Capability
