# Skill: Requirements Validation Verify Traceability

## Purpose
Validate requirements completeness, clarity, testability, and traceability to stakeholder needs.

## Inputs
- functional-requirements
- non-functional-requirements
- acceptance-criteria
- stakeholder-analysis-document

## Process

### 1. Load All Requirements
Read all requirement documents:
- functional-requirements.md
- non-functional-requirements.md
- acceptance-criteria.md
- stakeholder-analysis-document

### 2. Verify Completeness
Check that:
- Every stakeholder need is addressed by at least one requirement
- Every business objective has corresponding functional requirements
- All user journeys are covered
- No orphaned requirements (requirements without stakeholder justification)

### 3. Check Clarity
For each requirement:
- No ambiguous language ("should", "might", "could", "etc.")
- No vague terms ("user-friendly", "fast", "reliable")
- Clear subject, action, and condition
- Uniquely identifiable (has ID)

Flag any requirement that:
- Uses subjective language
- Lacks measurable criteria
- Is open to interpretation

### 4. Validate Testability
For each requirement:
- Can it be verified through testing, inspection, or demonstration?
- Are the acceptance criteria specific and measurable?
- Is the expected behavior clearly defined?

Requirements that cannot be tested must be rewritten or removed.

### 5. Check Consistency
- No conflicting requirements
- No duplicate requirements
- Terminology is consistent across all documents
- Requirements are at the same level of detail

### 6. Verify Traceability
Create a traceability matrix mapping:
- Business Objective → Capability → Requirement → Acceptance Criterion → Test Scenario

For each requirement, document:
- Source stakeholder(s)
- Business objective it supports
- Related requirements (depends on, conflicts with)
- Acceptance criteria coverage

### 7. Identify Gaps
Flag missing:
- Requirements for error handling
- Requirements for edge cases
- Requirements for data validation
- Requirements for security and access control
- Requirements for logging and monitoring

### 8. Produce Validation Report
Create two documents:
1. **traceability-map.md** - Complete traceability matrix
2. **validation-report.md** - Summary of findings:
   - Completeness score
   - Clarity issues found
   - Testability issues found
   - Consistency issues found
   - Gaps identified
   - Recommendations for improvement

## Output
- traceability-map.md
- validation-report.md

## Quality Criteria
- **Completeness**: All requirements are traced to sources
- **Objectivity**: Findings are based on evidence, not opinion
- **Actionability**: Every issue has a clear recommendation
- **Traceability**: Every check is traceable to a stakeholder need