# Testing Standards

## Purpose

Every feature should be accompanied by automated tests appropriate to its level of risk.

Tests provide confidence that future changes do not introduce regressions.  This requires 100% unit test coverage.

---

# Test Philosophy

Test behaviour rather than implementation.

A passing test should demonstrate that the software behaves correctly from the perspective of the caller.

---

# Unit Tests

Unit tests should:

- be fast
- be isolated 
- be mocked to ensure that any failure can only be due to the code under test.
- Test classes to create re-use using testing patterns should be used.

Mock external services.

---

# Integration Tests

Integration tests should verify:

- capability interactions
- API contracts
- workflow execution
- persistence

Prefer real integrations where practical.

Test classes may be used to set up and tear down common test data, so that known states can easily be understood.

---

# End-to-End Tests

Critical workflows should have end-to-end tests.

These should validate:

- expected inputs
- expected outputs
- error handling

---

# Naming

Test names should describe behaviour.

Good:

test_creates_session_when_none_exists()

test_returns_existing_session()

Poor:

test_session()

test_1()

---

# Assertions

Each test should verify one logical outcome only.  This needs to be the case, so that a failing test indicates exactly which piece of code failed, and why.  If that cannot be determined, then the test should bbe re-written to make that clear, to remove any assumptions, as each assumption is tested first.

Avoid excessive assertions in a single test.

---

# Arrange / Act / Assert

Tests should follow:

Arrange

Act

Assert

---

# Determinism

Tests must be repeatable.

Avoid relying on current time, randomness or external systems.

Inject clocks and random generators where required.

---

# Fixtures

Reuse fixtures.

Avoid duplicated setup code.

---

# Error Cases

Every public API should have tests covering:

- invalid input
- missing data
- permission failures
- provider failures
- unexpected exceptions

---

# AI Development

AI-generated code must include appropriate tests.

If testing cannot reasonably be performed, explain why.

Never claim code is tested unless tests have actually been executed.

Never fabricate test results.

Report test failures honestly.