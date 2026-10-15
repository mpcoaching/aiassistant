# Skill: Test Report

## Purpose
Generate comprehensive test reports and quality metrics that provide stakeholders with clear visibility into system quality and test coverage.

## Inputs
- test-results
- defect-reports
- test-coverage-data
- quality-metrics

## Process

### 1. Collect Test Data
Gather all test execution data:
- Test case execution results (pass/fail/blocked/skipped)
- Test execution timestamps and durations
- Defect reports and their status
- Test coverage metrics
- Performance test results
- Environment details

### 2. Calculate Test Metrics
Compute key quality metrics:
- **Test Execution Metrics**:
  - Total test cases
  - Executed/Not executed
  - Pass/Fail/Blocked/Skipped counts
  - Pass rate percentage
  - Execution time

- **Defect Metrics**:
  - Total defects found
  - Defects by severity (Critical/High/Medium/Low)
  - Defects by priority (P1/P2/P3/P4)
  - Defects by status (Open/In Progress/Fixed/Verified/Closed)
  - Defect density (defects per feature/component)
  - Mean time to detect (MTTD)
  - Mean time to resolve (MTTR)

- **Coverage Metrics**:
  - Requirements coverage (% of requirements with tests)
  - Code coverage (% of code executed by tests)
  - Test case coverage (% of acceptance criteria covered)
  - Branch coverage (if applicable)
  - Path coverage (if applicable)

- **Quality Indicators**:
  - Defect escape rate (defects found in production)
  - Test automation percentage
  - Flaky test rate
  - Test stability index

### 3. Analyze Results
- Identify trends in test results
- Identify defect patterns and root causes
- Identify areas of low coverage
- Identify flaky or unreliable tests
- Compare against quality gates
- Assess overall system quality

### 4. Create Test Execution Report
Create `test-execution-report.md`:

```markdown
# Test Execution Report

## Executive Summary
- **Feature/Release**: [Name]
- **Test Period**: [Start Date] - [End Date]
- **Overall Status**: [Pass/Fail/Blocked]
- **Quality Gate**: [Met/Not Met]

## Test Execution Summary

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Total Test Cases | - | [N] | - |
| Executed | - | [N] | - |
| Passed | - | [N] ([%]) | [✓/✗] |
| Failed | - | [N] ([%]) | [✓/✗] |
| Blocked | - | [N] ([%]) | [✓/✗] |
| Skipped | - | [N] ([%]) | [✓/✗] |
| Pass Rate | [%] | [%] | [✓/✗] |

## Defect Summary

| Severity | Count | Open | Fixed | Verified |
|----------|-------|------|-------|----------|
| Critical | [N] | [N] | [N] | [N] |
| High | [N] | [N] | [N] | [N] |
| Medium | [N] | [N] | [N] | [N] |
| Low | [N] | [N] | [N] | [N] |

## Test Coverage

| Coverage Type | Target | Actual | Status |
|---------------|--------|--------|--------|
| Requirements | [%] | [%] | [✓/✗] |
| Code | [%] | [%] | [✓/✗] |
| Acceptance Criteria | [%] | [%] | [✓/✗] |

## Defect Details

### Critical Defects
[List critical defects with brief description]

### High Priority Defects
[List high priority defects]

### Defect Trends
[Analysis of defect patterns, root causes, etc.]

## Test Execution Details

### By Feature/Component
[Breakdown of test results by feature]

### By Test Type
- Unit Tests: [N passed, N failed]
- Integration Tests: [N passed, N failed]
- E2E Tests: [N passed, N failed]
- Performance Tests: [N passed, N failed]

## Quality Assessment

### Strengths
[What went well]

### Weaknesses
[Areas of concern]

### Risks
[Quality risks for release]

### Recommendations
[Actions to improve quality]

## Appendices
- Detailed test results
- Defect reports
- Test coverage reports
- Performance test results
```

### 5. Create Quality Metrics Dashboard
Create `quality-metrics.md`:

```markdown
# Quality Metrics Dashboard

## Current Sprint/Release Quality Status

### Overall Quality Score: [X/10]

### Key Metrics
- **Test Pass Rate**: [%] (Target: [%])
- **Code Coverage**: [%] (Target: [%])
- **Requirements Coverage**: [%] (Target: [%])
- **Defect Density**: [N] defects per KLOC
- **Critical Defects**: [N] (Target: 0)
- **Open Defects**: [N] (Target: < [N])

### Trend Analysis
[Show trends over time for key metrics]

### Quality Gates Status
- [ ] Gate 1: Unit test coverage >= 80%
- [ ] Gate 2: Integration tests passing
- [ ] Gate 3: No critical defects
- [ ] Gate 4: Performance tests passing
- [ ] Gate 5: Security scan clean

### Action Items
[List any quality actions needed]
```

### 6. Create Defect Summary Report
Create `defect-summary.md`:
- List all defects found
- Categorize by severity and priority
- Identify defect clusters
- Track defect resolution progress
- Highlight critical blockers

### 7. Generate Coverage Reports
- Requirements coverage matrix
- Code coverage report (from coverage tools)
- Test case coverage by feature
- Gap analysis (uncovered requirements/code)

### 8. Executive Summary
Create executive-level summary:
- Overall quality assessment
- Key risks and blockers
- Go/No-Go recommendation
- Critical actions required

## Output
- test-execution-report.md
- quality-metrics.md
- defect-summary.md
- coverage-reports/
- executive-summary.md

## Quality Criteria
- **Accuracy**: Metrics are calculated correctly
- **Completeness**: All test results are included
- **Clarity**: Reports are easy to understand
- **Actionability**: Issues are clearly identified with recommendations
- **Timeliness**: Reports are generated promptly after test execution
- **Traceability**: All metrics trace back to test cases and requirements

## Report Distribution
- **Development Team**: Detailed test results and defect reports
- **Test Team**: Test execution metrics and coverage reports
- **Project Management**: Quality metrics and progress
- **Executive Sponsors**: Executive summary and go/no-go recommendation