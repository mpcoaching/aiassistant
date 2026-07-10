# Skill: Development Write Tests

## Purpose
Write comprehensive tests for implemented code following TDD/BDD practices to ensure quality and prevent regressions.

## Inputs
- implemented-code
- acceptance-criteria
- requirements

## Process

### 1. Review Code and Requirements
Read:
- The implemented code
- Acceptance criteria for the feature
- Functional requirements being addressed
- Edge cases identified in requirements

### 2. Identify Test Scenarios
For each acceptance criterion:
- **Happy path**: Normal successful execution
- **Error paths**: Expected failures and error conditions
- **Edge cases**: Boundary conditions, null values, empty inputs
- **Integration points**: Interactions with external systems
- **Performance scenarios**: Load, stress, and scalability tests (if needed)

### 3. Write Unit Tests
For each function/method:
- Test the happy path
- Test error conditions
- Test boundary values
- Test with invalid inputs
- Mock external dependencies
- Aim for high coverage (80%+)

Follow the AAA pattern:
- **Arrange**: Set up test data and conditions
- **Act**: Execute the function/method
- **Assert**: Verify the expected outcome

Example structure:
```python
def test_function_happy_path():
    # Arrange
    input_data = create_test_data()
    expected_output = create_expected_output()
    
    # Act
    actual_output = function_under_test(input_data)
    
    # Assert
    assert actual_output == expected_output
```

### 4. Write Integration Tests
For component interactions:
- Test API endpoints with real HTTP requests
- Test database operations with test database
- Test message queue interactions
- Test external service integrations (with mocks or test instances)
- Verify data flows correctly between components

### 5. Write End-to-End Tests (if applicable)
For critical user journeys:
- Test complete workflows from user perspective
- Use UI automation tools (Selenium, Playwright, etc.)
- Test across different browsers/devices
- Verify system behavior as a whole

### 6. Test Edge Cases
Specifically test:
- Null/None values
- Empty strings/lists
- Maximum/minimum values
- Invalid data types
- Concurrent access (if applicable)
- Network failures (for distributed systems)

### 7. Ensure Test Quality
Each test should be:
- **Independent**: Can run in any order
- **Repeatable**: Produces same results every time
- **Fast**: Executes quickly
- **Self-checking**: Automatically verifies results
- **Timely**: Written before or with the code

### 8. Run Tests and Verify
- Run all tests
- Verify all tests pass
- Check test coverage meets requirements (80%+)
- Fix any failing tests
- Refactor tests for clarity if needed

### 9. Document Test Strategy
Create test documentation:
- Test approach and tools used
- Test coverage report
- Known limitations
- Manual testing steps (if any)

## Output
- unit-tests/ (directory with unit test files)
- integration-tests/ (directory with integration test files)
- e2e-tests/ (directory with end-to-end tests, if applicable)
- test-results.md (summary of test execution)

## Quality Criteria
- **Coverage**: Meets minimum coverage requirement (80%+)
- **Completeness**: All acceptance criteria have tests
- **Independence**: Tests don't depend on each other
- **Readability**: Tests are clear and well-named
- **Maintainability**: Tests are easy to update when code changes
- **Speed**: Test suite runs in reasonable time