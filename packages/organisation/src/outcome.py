"""
Outcome assessment and learning helpers (Increment 10).

Provides functions to assess execution results against acceptance criteria
and record durable learning in EIMS.

These are organisational concerns, not operational execution concerns.
"""

from __future__ import annotations

from typing import Any


def assess_work_outcome(
    work: Any,
    execution_result: dict[str, Any],
) -> dict[str, Any]:
    """Assess an execution result against Work acceptance criteria.

    Args:
        work: The Work item being assessed.
        execution_result: Raw execution result from Operations.

    Returns:
        Assessed outcome dict containing:
        - accepted: bool
        - execution_result: the raw result
        - criteria_met: list of criteria that were met
        - criteria_failed: list of criteria that were not met
        - rationale: explanation of the assessment
    """
    criteria = work.acceptance_criteria or []
    outputs = execution_result.get("outputs", {})
    output_summary = str(outputs.get("summary", outputs))

    criteria_met = []
    criteria_failed = []
    for criterion in criteria:
        if criterion.lower() in output_summary.lower():
            criteria_met.append(criterion)
        else:
            criteria_failed.append(criterion)

    accepted = len(criteria_failed) == 0 and execution_result.get("status") == "completed"

    return {
        "accepted": accepted,
        "execution_result": execution_result,
        "criteria_met": criteria_met,
        "criteria_failed": criteria_failed,
        "rationale": (
            f"All {len(criteria_met)} criteria met."
            if accepted
            else f"{len(criteria_failed)} criteria not met."
        ),
    }


def record_work_learning(
    work: Any,
    outcome_assessment: dict[str, Any],
    store: Any,
) -> Any | None:
    """Record durable learning from a completed Work item in EIMS.

    Only records if:
    - Work is accepted
    - Work has durable enterprise value (project/initiative, not routine BAU)

    Uses dynamic import to avoid importing concepts into the organisation
    package, preserving the organisational boundary.
    """
    if not outcome_assessment.get("accepted"):
        return None

    if work.work_type not in ("project", "initiative"):
        return None

    concepts = __import__("concepts", fromlist=["ConceptKind", "EnterpriseConcept"])
    ConceptKind = concepts.ConceptKind
    EnterpriseConcept = concepts.EnterpriseConcept


    concept = EnterpriseConcept(
        id=f"work-outcome-{work.id}",
        kind=ConceptKind.SOLVED_APPROACH,
        name=work.title,
        description=f"Outcome of {work.work_type}: {work.title}",
        tags=["work_outcome", work.work_type, f"role:{work.accountable_role_id}"],
        payload={
            "summary": outcome_assessment.get("rationale", ""),
            "work_id": work.id,
            "work_type": work.work_type,
            "accountable_role_id": work.accountable_role_id,
            "coordinating_role_id": work.coordinating_role_id,
            "outcome": work.outcome,
            "acceptance_criteria": work.acceptance_criteria,
            "criteria_met": outcome_assessment.get("criteria_met", []),
            "criteria_failed": outcome_assessment.get("criteria_failed", []),
        },
    )
    store.upsert(concept)
    return concept
