# Skill: Development Refactor

## Purpose
Refactor implemented code to improve quality, maintainability, and performance while preserving functionality.

## Inputs
- implemented-code
- unit-tests
- code-quality-issues

## Process

### 1. Review Code and Tests
Read:
- The implemented code
- Unit tests (ensure they pass before refactoring)
- Code quality issues identified (if any)
- Coding standards and best practices

### 2. Identify Code Smells
Look for:
- **Long methods**: Functions that are too long (>20 lines)
- **Large classes**: Classes with too many responsibilities
- **Duplicate code**: Copy-pasted code blocks
- **Long parameter lists**: Functions with too many parameters
- **Feature envy**: Methods that use more features of another class
- **Data clumps**: Groups of parameters that always appear together
- **Primitive obsession**: Overuse of primitives instead of small objects
- **Switch statements**: Complex conditional logic
- **Speculative generality**: Unused code or over-engineering

### 3. Plan Refactoring
For each code smell:
- Identify the refactoring technique to apply
- Ensure tests will still pass after refactoring
- Prioritize refactorings by impact and risk
- Break large refactorings into small steps

### 4. Apply Refactoring Techniques
Common refactorings:
- **Extract Method**: Break long methods into smaller ones
- **Extract Class**: Split large classes into smaller, focused classes
- **Rename**: Improve variable, method, and class names
- **Move Method/Field**: Move methods/fields to more appropriate classes
- **Replace Conditional with Polymorphism**: Use polymorphism instead of switch/if-else
- **Introduce Parameter Object**: Replace parameter lists with objects
- **Remove Duplication**: Extract common code into reusable functions
- **Simplify Conditional Logic**: Break down complex conditions
- **Replace Magic Numbers with Constants**: Use named constants
- **Encapsulate Field**: Make fields private with getters/setters

### 5. Refactor Incrementally
For each refactoring:
1. Make a small change
2. Run tests to ensure they still pass
3. Commit the change
4. Repeat

Never refactor and add features at the same time.

### 6. Improve Code Structure
- **Single Responsibility**: Each class/function does one thing
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Subtypes are substitutable for base types
- **Interface Segregation**: Small, focused interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

### 7. Optimize Performance (if needed)
- Profile code to identify bottlenecks
- Optimize hot paths
- Reduce unnecessary computations
- Improve data structures
- Cache expensive operations

### 8. Update Documentation
- Update comments to reflect changes
- Update API documentation
- Update README if needed
- Document any breaking changes

### 9. Final Verification
- Run all tests (unit, integration, e2e)
- Verify all tests pass
- Check test coverage hasn't decreased
- Run linting/static analysis
- Verify no functionality was broken

## Output
- refactored-code
- updated-tests (if needed)
- refactoring-notes.md (summary of changes)

## Quality Criteria
- **Functionality**: All tests pass, no behavior changed
- **Readability**: Code is easier to understand
- **Maintainability**: Code is easier to modify
- **Performance**: No performance degradation (improvement if possible)
- **Testability**: Code is easier to test
- **Standards**: Follows coding standards
- **Documentation**: Changes are documented

## Refactoring Principles
- **Boy Scout Rule**: Leave code better than you found it
- **Small Steps**: Make small, incremental changes
- **Test First**: Ensure tests pass before and after each change
- **No Behavior Change**: Refactoring should not change functionality
- **Continuous**: Refactor regularly, not just in dedicated sprints