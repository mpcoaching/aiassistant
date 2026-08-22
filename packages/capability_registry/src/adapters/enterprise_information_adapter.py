"""
Adapter: contracts.EnterpriseInformationPort -> ConceptStore.

Wraps ConceptStore queries for previous solutions and solution recording.
This is the only place in capability_registry that knows about ConceptStore.
"""

from __future__ import annotations

from contracts.enterprise_information import PreviousSolution, SolutionRecord
from concepts import ConceptStore, EnterpriseConcept


class EnterpriseInformationAdapter:
    def __init__(self, store: ConceptStore) -> None:
        self._store = store

    def find_previous_solutions(self, strategy_tag: str) -> PreviousSolution | None:
        concepts = self._store.list_by_tag(strategy_tag)
        if not concepts:
            return None
        concept = concepts[0]
        payload = concept.payload or {}
        maturation = payload.get("maturation_history", {})
        return PreviousSolution(
            concept_id=concept.id,
            name=concept.name,
            summary=concept.description,
            invocation_count=maturation.get("invocation_count", 0),
            last_invoked=maturation.get("last_invoked_at"),
        )

    def record_solution(self, solution: SolutionRecord) -> None:
        concept = EnterpriseConcept(
            id=f"sol-{solution.strategy}",
            name=solution.strategy,
            description=solution.summary,
            owner="system",
            created_by="ai",
            status="active",
            tags=[solution.strategy, "solution"],
            payload={
                "maturation_history": {
                    "invocation_count": solution.invocation_count,
                    "correction_count": 0,
                    "last_invoked_at": None,
                },
                "outputs": solution.outputs,
                "pattern_pipeline": solution.pattern_pipeline,
            },
        )
        self._store.upsert(concept)
