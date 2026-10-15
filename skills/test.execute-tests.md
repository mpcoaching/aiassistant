# Skill: Test Execute Tests

## Purpose
Execute manual and automated tests, capture results, and report defects with clear reproduction steps.

## Inputs
- test-cases
- test-data
- implemented-code
- test-environment

## Process

### 1. Prepare Test Environment
- Set up test environment (dev/staging/prod)
- Deploy application under test
- Prepare test data
- Configure test tools and frameworks
- Verify environment is ready for testing

### 2. Review Test Cases
Read:
- Test scenarios and test cases
- Acceptance criteria
- Expected results
- Test data requirements

### 3. Execute Manual Tests
For each test case:
1. **Verify preconditions**: Ensure all prerequisites are met
2. **Execute test steps**: Follow steps exactly as written
3. **Observe actual result**: Document what actually happens
4. **Compare with expected**: Determine if test passes or fails
5. **Record result**: Update test case with actual result and status

For failed tests:
- Document exact steps to reproduce
- Capture screenshots/videos
- Note error messages
- Record environment details
- Assess severity and priority

### 4. Execute Automated Tests
- Run automated test suites
- Monitor test execution
- Capture test results
- Investigate failures
- Re-run flaky tests to confirm

For automated test failures:
- Review test logs
- Identify if failure is code defect or test issue
- Document findings
- Update test if needed

### 5. Perform Exploratory Testing
Beyond scripted tests:
- Explore edge cases not in test cases
- Try unusual user behaviors
- Test error handling
- Verify security controls
- Check performance under load
- Test across different browsers/devices

### 6. Execute Integration Tests
- Test API endpoints
- Test database operations
- Test message queue interactions
- Test external service integrations
- Verify data flows correctly

### 7. Execute Performance Tests (if applicable)
- Run load tests
- Monitor system metrics (CPU, memory, response time)
- Identify performance bottlenecks
- Verify system meets NFRs
- Document performance results

### 8. Report Defects
For each defect found:
- **Title**: Clear, concise description
- **Severity**: Critical/High/Medium/Low
- **Priority**: P1/P2/P3/P4
- **Environment**: Where defect was found
- **Steps to Reproduce**: Numbered steps
- **Expected Result**: What should happen
- **Actual Result**: What actually happened
- **Evidence**: Screenshots, videos, logs
- **Additional Context**: Related information

Use defect tracking system (Jira, GitHub Issues, etc.)

### 9. Track Test Progress
- Update test case status (Pass/Fail/Blocked/Skipped)
- Track test execution metrics
- Monitor test coverage
- Identify blocking issues
- Report progress to stakeholders

### 10. Document Test Execution
Create test execution summary:
- Total tests executed
- Tests passed/failed/blocked/skipped
- Defects found (by severity)
- Test coverage achieved
- Risks and issues
- Recommendations

## Output
- test-results/ (directory with detailed test results)
- defect-reports/ (directory with defect reports)
- test-execution-summary.md

## Quality Criteria
- **Completeness**: All test cases are executed
- **Accuracy**: Results accurately reflect system behavior
- **Traceability**: Each result links to a test case
- **Clarity**: Defects are clearly documented with reproduction steps
- **Timeliness**: Results are reported promptly
- **Objectivity**: Results are based on evidence, not opinion

## Test Execution Best Practices
- **Isolation**: Test in clean environment
- **Repeatability**: Tests can be re-run with same results
- **Independence**: Tests don't affect each other
- **Documentation**: Everything is documented
- **Communication**: Defects are reported immediately
- **Verification**: Fixes are verified before closing defects