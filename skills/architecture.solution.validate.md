# Skill: Architecture Solution Validate

## Purpose
Validate a completed solution architecture against enterprise standards, constraints, requirements, and architecture principles. Identify risks, gaps, and inconsistencies before implementation begins.

## Inputs
- solution architecture document
- architecture context document
- enterprise architecture principles and standards
- ADRs (Architecture Decision Records)
- requirements documents
- constraints
- coding and design standards

## Process

### 1. Compliance Check
Verify the solution architecture conforms to:
- Enterprise architecture principles and standards
- Technology direction and approved patterns
- Security policies and compliance requirements
- Organisational constraints

### 2. Requirements Traceability
For each key requirement:
- Verify it is addressed in the solution architecture
- Check that the architectural approach satisfies the requirement
- Identify any requirements that are not addressed or are only partially addressed
- Flag any architectural decisions that conflict with stated requirements

### 3. ADR Consistency
Review the solution's architecture decisions against existing ADRs:
- Are new decisions consistent with previous ADRs?
- Do any previous ADRs need to be revisited or updated?
- Are new decisions properly documented with rationale and alternatives?
- Is the decision record complete and auditable?

### 4. Risk Assessment
Identify and classify risks:
- **Technical risks**: Feasibility, performance, scalability, security
- **Integration risks**: Dependencies on external systems, data flow complexity
- **Implementation risks**: Organisational capability, timeline, complexity
- **Operational risks**: Maintainability, observability, deployment complexity

For each risk, document:
- Description and impact
- Likelihood (low/medium/high)
- Proposed mitigation or acceptance rationale

### 5. Gap Analysis
Identify gaps in the solution architecture:
- Missing components or capabilities
- Undefined interfaces or integration points
- Unaddressed non-functional requirements
- Incomplete data models or schemas
- Missing deployment or operational considerations

### 6. Implementation Feasibility
Assess whether the architecture can be implemented:
- Is the architecture sufficiently detailed for implementation to begin?
- Are there clear component boundaries and interfaces?
- Is the deployment model defined and achievable?
- Are there any technology or skill gaps that would block implementation?

### 7. Produce Validation Report
Output a structured validation report containing:
- **Summary**: Overall assessment (approved / approved with conditions / rejected)
- **Compliance Results**: Checklist of standards and principles checked
- **Traceability Matrix**: Requirements mapped to architectural decisions
- **Risk Register**: Identified risks with classifications
- **Gap Analysis**: Missing or incomplete elements
- **Findings**: Specific issues requiring resolution
- **Recommendations**: Actions to address findings
- **Conditions for Approval**: If approved with conditions, what must be resolved

## Output
- validation-report

## Quality Criteria
- **Objectivity**: Findings are based on evidence, not opinion
- **Actionability**: Every finding includes a clear recommendation
- **Traceability**: Every check is traceable to a specific standard or requirement
- **Completeness**: All relevant standards and requirements are checked
- **Proportionality**: Severity of findings matches actual risk level