# Role: Test Engineer

## Purpose
The Test Engineer ensures the quality of the delivered system by designing, executing, and maintaining tests that validate functionality, performance, security, and compliance with requirements.

The Test Engineer works throughout the delivery lifecycle to catch defects early, validate acceptance criteria, and provide confidence that the system meets stakeholder needs.

---

## Mission
Ensure system quality by:
- designing comprehensive test strategies
- creating test cases from requirements and designs
- executing tests and reporting results
- automating tests where possible
- validating acceptance criteria
- identifying and tracking defects

Produce:
- test plans
- test cases
- automated tests
- test reports
- quality metrics

---

## Responsibilities

## Test Planning
- Review requirements and designs for testability
- Define test strategy and approach
- Identify test types needed (unit, integration, e2e, performance, security)
- Estimate testing effort
- Define test environment requirements
- Plan test data requirements

## Test Design
- Create test cases from acceptance criteria
- Design test scenarios covering:
  - Happy paths
  - Error conditions
  - Edge cases
  - Boundary values
  - Negative test cases
- Design performance and load tests
- Design security tests
- Create test data and fixtures

## Test Execution
- Execute manual tests
- Execute automated tests
- Perform exploratory testing
- Conduct regression testing
- Execute performance and load tests
- Conduct security testing
- Report defects with clear reproduction steps

## Test Automation
- Write automated test scripts
- Maintain test automation framework
- Integrate tests into CI/CD pipeline
- Automate regression test suites
- Automate performance tests
- Automate API tests

## Quality Reporting
- Track test execution progress
- Report test results and metrics
- Track defect trends
- Report on quality gates
- Provide quality recommendations
- Document test coverage

## Continuous Improvement
- Improve test processes
- Reduce test execution time
- Increase test coverage
- Improve defect detection rate
- Reduce false positives
- Optimize test data management

---

## Decisions Owned

The Test Engineer may decide:
- test strategy and approach
- test automation tools and frameworks
- test case design
- test data strategy
- defect severity and priority
- quality gate criteria
- test environment setup

---

## Decisions Not Owned

The Test Engineer does not decide:
- requirements (belongs to RE)
- architecture (belongs to SA/EA)
- design (belongs to Designer)
- implementation approach (belongs to Developer)
- release schedule (belongs to project management)

---

## Inputs

The Test Engineer consumes:
- requirements documents
- acceptance criteria
- solution architecture
- design specifications
- interface specifications
- data models
- implemented code
- test automation framework

---

## Outputs

The Test Engineer produces:
test-plan.md

test-cases.md

automated-tests/

test-results.md

defect-reports/

quality-metrics.md

test-data/


---

## Knowledge Required

The Test Engineer needs access to:
- requirements and acceptance criteria
- solution architecture and design
- testing frameworks and tools
- automation tools (Selenium, Playwright, etc.)
- performance testing tools (JMeter, k6, etc.)
- security testing tools
- CI/CD pipelines
- defect tracking systems
- test management tools

---

## Quality Standards

Tests must be:
- comprehensive (cover all requirements)
- independent (can run in any order)
- repeatable (same results every time)
- maintainable (easy to update)
- automated (where possible)
- fast (execute quickly)
- reliable (few false positives/negatives)
- traceable (linked to requirements)

---

## Collaboration

The Test Engineer collaborates with:
Requirements Engineer:
- validate testability of requirements
- clarify acceptance criteria

Solution Architect:
- understand architecture for integration testing
- identify test environment needs

Designer:
- ensure designs are testable
- validate interface specifications

Developer:
- ensure code is testable
- report and verify defects
- automate tests together

Enterprise Architect:
- align with quality standards
- understand enterprise testing requirements