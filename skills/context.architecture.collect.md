# Skill: Context Architecture Collect

## Purpose
Gather, analyse, and synthesise all input materials into a structured Architecture Context document that removes ambiguity before solution design begins.

## Inputs
- requirements documents
- enterprise architecture documentation
- ADRs (Architecture Decision Records)
- system context
- constraints
- standards
- stakeholder concerns
- technical strategy documents

## Process

### 1. Gather Inputs
Collect all available input materials. Identify what is present and what is missing.

### 2. Analyse Enterprise Context
Review the enterprise architecture to understand:
- Strategic direction and business capabilities
- Architecture principles and standards
- Existing technology direction and approved patterns
- Cross-solution dependencies and integration points

### 3. Extract Driving Requirements
From the requirements documents, identify:
- Primary business objectives the solution must address
- Functional requirements that shape the architecture
- Non-functional requirements (performance, scalability, security, availability)
- Constraining requirements that limit design choices

### 4. Review Architecture Decisions
Examine relevant ADRs to identify:
- Previous decisions that constrain or influence this solution
- Decision context and rationale
- Alternatives that were considered and rejected
- Any ADRs that may need revision

### 5. Identify Constraints and Standards
Document the boundaries within which the solution must be designed:
- Technology constraints (approved platforms, languages, vendors)
- Compliance and regulatory requirements
- Security policies
- Integration constraints with existing systems
- Organisational capability constraints

### 6. Identify Stakeholder Concerns
For each stakeholder group, identify:
- Primary concerns and priorities
- Success criteria
- Risk tolerance
- Timeline expectations

### 7. Synthesise Architecture Context
Produce a structured Architecture Context document containing:
- **Executive Summary**: Brief overview of the architectural problem
- **Business Context**: Strategic objectives and capabilities
- **Requirements Summary**: Key driving requirements and constraints
- **Enterprise Context**: Relevant enterprise architecture references
- **Technology Landscape**: Current state and direction
- **Stakeholder Concerns**: Mapped to architectural drivers
- **Constraints and Standards**: Explicit boundaries
- **Assumptions**: Clearly marked assumptions made during analysis
- **Open Issues**: Gaps or ambiguities requiring resolution before design

## Output
- architecture-context document

## Quality Criteria
- **Completeness**: All input materials are referenced
- **Traceability**: Every statement is traceable to a source
- **Neutrality**: Context describes what is, not what the solution should be
- **Clarity**: Assumptions are explicitly marked as such
- **Structure**: Ready to be consumed by the solution design skill