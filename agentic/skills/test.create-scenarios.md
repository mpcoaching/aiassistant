# Skill: Test Create Scenarios

## Purpose
Create comprehensive test scenarios and test cases from requirements, designs, and acceptance criteria.

## Inputs
- acceptance-criteria
- requirements
- design-specifications
- interface-specification

## Process

### 1. Review Requirements and Designs
Read:
- Acceptance criteria
- Functional requirements
- Design specifications
- Interface specifications
- Data models

### 2. Identify Test Conditions
For each requirement/acceptance criterion:
- Identify what needs to be tested
- Determine test conditions (the thing to be verified)
- Consider both functional and non-functional aspects

### 3. Design Test Cases
For each test condition, create test cases covering:
- **Happy path**: Normal, expected behavior
- **Error paths**: Expected error conditions
- **Edge cases**: Boundary conditions, limits
- **Negative tests**: Invalid inputs, unauthorized access
- **Integration points**: Interactions with external systems

### 4. Structure Test Cases
Each test case should include:
- **Test ID**: Unique identifier (TC-001, TC-002, etc.)
- **Test Title**: Brief description
- **Priority**: High/Medium/Low
- **Preconditions**: What must be true before test
- **Test Steps**: Step-by-step instructions
- **Expected Result**: What should happen
- **Actual Result**: What actually happened (filled during execution)
- **Status**: Pass/Fail/Blocked (filled during execution)

Example:
```markdown
### TC-001: User can login with valid credentials

**Priority**: High
**Preconditions**: User account exists in system

**Test Steps**:
1. Navigate to login page
2. Enter valid username
3. Enter valid password
4. Click "Login" button

**Expected Result**: 
- User is redirected to dashboard
- Welcome message displays user's name
- Session token is created

**Actual Result**: 
**Status**: 
```

### 5. Organize Test Cases
Group test cases by:
- Feature/functionality
- Test type (functional, integration, e2e)
- Priority
- Test environment

### 6. Define Test Data Requirements
For each test case:
- Identify required test data
- Specify data values or ranges
- Identify data setup steps
- Document data cleanup requirements

### 7. Create Test Scenarios Document
Create `test-scenarios.md` with:

```markdown
# Test Scenarios

## Test Strategy
[Overall approach to testing this feature]

## Test Environment
- Environment: [dev/staging/prod]
- Browser: [Chrome, Firefox, Safari, etc.]
- Devices: [Desktop, Mobile, Tablet]
- Test data: [Where test data comes from]

## Test Cases

### [Feature/Functionality Name]

#### TC-001: [Test Title]
- **Priority**: [High/Medium/Low]
- **Type**: [Functional/Integration/E2E/Performance/Security]
- **Preconditions**: [What must be true]
- **Test Steps**:
  1. [Step 1]
  2. [Step 2]
  3. [Step 3]
- **Expected Result**: [What should happen]
- **Test Data**: [Required data]
- **Notes**: [Any additional context]

## Traceability Matrix
| Requirement ID | Test Case ID | Status |
|----------------|--------------|--------|
| FR-001 | TC-001, TC-002 | Covered |
| FR-002 | TC-003 | Covered |
```

### 8. Review and Refine
- Review test cases for completeness
- Ensure all acceptance criteria are covered
- Check for duplicate test cases
- Validate test cases are executable
- Get stakeholder approval if needed

## Output
- test-scenarios.md
- test-cases.md (detailed test cases)
- test-data-requirements.md

## Quality Criteria
- **Completeness**: All requirements and acceptance criteria have test cases
- **Coverage**: Happy paths, error paths, and edge cases are covered
- **Clarity**: Test steps are clear and unambiguous
- **Executability**: Tests can be executed as written
- **Traceability**: Each test case links to a requirement or acceptance criterion
- **Independence**: Tests don't depend on each other