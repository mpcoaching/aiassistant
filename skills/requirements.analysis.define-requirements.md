# Skill: Requirements Analysis Define Requirements

## Purpose
Transform stakeholder analysis into structured, implementation-ready requirements documentation.

## Inputs
- stakeholder-analysis-document
- business-vision
- existing-documentation

## Process

### 1. Review Stakeholder Analysis
Read the stakeholder analysis document to understand:
- All identified stakeholders and their interests
- Key concerns and success criteria
- Business objectives and desired outcomes

### 2. Extract Functional Requirements
For each business objective and stakeholder need:
- Identify what the system must do
- Define functional capabilities in clear, testable statements
- Use the format: "The system shall [action] [condition]"
- Group by capability area or user journey

### 3. Extract Non-Functional Requirements
Identify quality attributes:
- Performance (response times, throughput)
- Scalability (concurrent users, data volume)
- Security (authentication, authorization, encryption)
- Availability (uptime, disaster recovery)
- Maintainability (code quality, documentation)
- Usability (accessibility, user experience)

### 4. Define Business Rules
Capture:
- Validation rules
- Calculation rules
- Workflow rules
- Authorization rules

### 5. Identify Data Requirements
- Data entities and their relationships
- Data retention requirements
- Data quality requirements
- Integration data needs

### 6. Define Acceptance Criteria
For each functional requirement:
- Given [context]
- When [action]
- Then [observable outcome]

Acceptance criteria must be:
- Testable
- Unambiguous
- Independent
- Negotiable

### 7. Document Requirements
Create three documents:
1. **functional-requirements.md** - All functional requirements with IDs (FR-001, FR-002, etc.)
2. **non-functional-requirements.md** - All NFRs with IDs (NFR-001, NFR-002, etc.)
3. **acceptance-criteria.md** - All acceptance criteria mapped to functional requirements

## Output
- functional-requirements.md
- non-functional-requirements.md
- acceptance-criteria.md

## Quality Criteria
- **Completeness**: All stakeholder needs are addressed
- **Clarity**: No ambiguous language ("should", "might", "could")
- **Testability**: Every requirement can be verified
- **Traceability**: Each requirement links to a stakeholder need
- **Consistency**: No conflicting requirements