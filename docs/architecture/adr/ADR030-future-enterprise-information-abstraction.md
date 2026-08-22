# ADR-030: Future EnterpriseInformation Abstraction for CEO

Status: Proposed

Decision

The CEO should eventually consume an EnterpriseInformation abstraction rather than accessing ConceptStore directly. This preserves the EIMS boundary and allows the EIMS implementation to evolve without changing CEO logic. Do NOT implement this abstraction in Increment 7 or 8 unless investigation proves it is immediately required.

Context

Currently, CEOAgent directly instantiates ConceptStore for EIMS reads (previous solution lookup). This couples the CEO to the current EIMS implementation. As EIMS evolves (expanding beyond ConceptStore), this coupling becomes a liability.

Investigation Finding

The CEO only uses ConceptStore for:
- `list_by_tag(strategy_tag)` — finding previous solutions by strategy tag
- Reading EnterpriseConcept payloads (maturation history, summary)

This is a read-only, query-oriented access pattern. It does not require the full ConceptStore API.

Decision

1. Document the future boundary: CEO should use an EnterpriseInformation interface with methods like:
   - `find_previous_solutions(strategy_tag: str) -> list[EnterpriseConcept]`
   - `get_concept(concept_id: str) -> EnterpriseConcept | None`

2. Do NOT implement this abstraction now. The current direct ConceptStore usage is acceptable for Increment 6 and proposed Increment 8 scope.

3. When implemented, the abstraction sits between CEO and ConceptStore:
   ```
   CEOAgent
      |
      | uses
      v
   EnterpriseInformation (future abstraction)
      |
      | implemented by
      v
   ConceptStore (current implementation)
      |
      | may evolve to
      v
   Future EIMS implementation
   ```

4. The abstraction must be owned by the Enterprise plane, not by the AI package.

Rationale

1. The CEO is an organisational role, not an EIMS owner. It should consume EIMS through an interface.
2. Preserving this boundary now prevents rushed coupling later.
3. Documenting the future abstraction makes the next refactor obvious and safe.
4. Increment 7 is an investigation increment; adding implementation would violate the scope.

Consequences

- CEO continues to use ConceptStore directly in Increment 8.
- Future increment introduces EnterpriseInformation abstraction.
- Organisation/Control plane may also consume EnterpriseInformation for organisational context.
- No immediate code changes required.

Related

- ADR-021: EIMS Boundary and ConceptStore as Current Implementation
- ADR-024: CEO as Organisational Role
- ADR-017: Three-Plane Architecture
