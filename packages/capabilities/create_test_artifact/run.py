"""
create_test_artifact capability (Increment 2).

Deterministic capability that creates a test artifact record
as an EnterpriseConcept and returns its identifier.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from capability_registry.src.concepts import ConceptKind, ConceptStore, EnterpriseConcept


def run(context: dict[str, Any]) -> dict[str, Any]:
    """Execute the capability.

    Args:
        context: Execution context. Expected keys:
            - label: str (required) — artifact label
            - concept_store_data_dir: str (optional) — ConceptStore directory

    Returns:
        dict with artifact_id, created_at, label, kind
    """
    label = context.get("label", "unnamed")
    data_dir = context.get("concept_store_data_dir", "./concepts_data")

    store = ConceptStore(data_dir=data_dir)

    concept = EnterpriseConcept(
        id=f"art-{uuid.uuid4().hex[:8]}",
        kind=ConceptKind.SOLVED_APPROACH,
        name=label,
        description=f"Test artifact: {label}",
        tags=["test", "artifact", "create_test_artifact"],
        payload={
            "label": label,
            "type": "test_artifact",
            "created_by": "capability:create_test_artifact",
        },
    )
    store.upsert(concept)

    return {
        "artifact_id": concept.id,
        "created_at": concept.created_at.isoformat(),
        "label": label,
        "kind": concept.kind.value,
    }
