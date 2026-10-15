# Skill: EA Architectural Discovery

## Purpose
Conduct Socratic discovery for a new subsystem and produce an Architecture Decision Record (ADR).

## Inputs
- subsystem-scope
- constraints
- existing-patterns

## Process

### 1. Understand the Scope
Read the subsystem scope document to understand:
- What problem this subsystem solves
- Boundaries and responsibilities
- Key stakeholders and their concerns
- Success criteria

### 2. Socratic Discovery
Ask 3-5 targeted questions to clarify:
- **Boundaries**: What is in/out of scope? Where are the integration points?
- **Dependencies**: What does this subsystem depend on? What depends on it?
- **Failure modes**: What happens when this subsystem fails? What are the recovery strategies?
- **Data ownership**: Who owns which data entities? What is the Source of Truth?
- **Constraints**: What technical, organizational, or regulatory constraints apply?

### 3. Verify Against Constraints
Ensure the proposed design adheres to:
- Enterprise architecture principles
- Technology standards and approved patterns
- Security policies
- Compliance requirements
- Organizational constraints

### 4. Identify Alternatives
For key architectural decisions:
- List 2-3 viable alternatives
- Document pros and cons of each
- Identify trade-offs (performance vs. complexity, cost vs. flexibility, etc.)

### 5. Make the Decision
Select the preferred approach and document:
- The decision made
- Rationale for the choice
- Why alternatives were rejected
- Risks and mitigations

### 6. Document Consequences
For the chosen approach:
- Positive consequences (benefits)
- Negative consequences (costs, risks)
- Neutral consequences (changes required)
- Impact on other systems

### 7. Reference Patterns and Templates
- Reference relevant patterns from `/patterns/`
- Reference relevant templates from `/templates/`
- Identify which enterprise building blocks (ABBs) are involved

### 8. Write the ADR
Create an ADR in `/docs/context/ea/adr/` with the following structure:

```markdown
# ADR-XXX: [Title]

## Status
[Proposed | Accepted | Rejected | Deprecated]

## Context
[Describe the problem, constraints, and driving forces]

## Decision
[State the decision clearly]

## Alternatives Considered
1. **Alternative 1**: [Description]
   - Pros: [list]
   - Cons: [list]
   
2. **Alternative 2**: [Description]
   - Pros: [list]
   - Cons: [list]

## Consequences
### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Cost 1]
- [Risk 1]

### Neutral
- [Change 1]
- [Change 2]

## References
- [Link to relevant patterns]
- [Link to relevant templates]
- [Link to related ADRs]
```

### 9. Present for Approval
Do not implement until the ADR is:
- Written and saved to `/docs/context/ea/adr/`
- Reviewed and approved by the user/stakeholder

## Output
- ADR document in `/docs/context/ea/adr/`
- Discovery questions log
- Decision rationale

## Quality Criteria
- **Completeness**: All significant decisions are documented
- **Clarity**: Decision and rationale are unambiguous
- **Traceability**: Decision is traceable to requirements and constraints
- **Reversibility**: Decision record allows future review and revision
- **Stakeholder alignment**: Decision is approved by relevant stakeholders