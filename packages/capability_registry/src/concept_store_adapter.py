"""
CapabilityRepository adapter wrapping ConceptStore (Increment 14).

Implements CapabilityRepository by delegating to ConceptStore.
This is the ONLY place in capability_registry that knows about ConceptStore.
"""

from __future__ import annotations

from typing import Any

from capability import Capability, CapabilityInterface, CapabilityStatus
from concepts import ConceptKind, ConceptStore, EnterpriseConcept


class ConceptStoreCapabilityRepository:
    """Adapts ConceptStore to CapabilityRepository protocol."""

    def __init__(self, store: ConceptStore | None = None) -> None:
        self._store = store or ConceptStore()

    def upsert_capability(self, capability: Capability) -> None:
        concept = EnterpriseConcept(
            id=capability.id,
            kind=ConceptKind.CAPABILITY,
            name=capability.name,
            description=capability.description,
            status=capability.status.value if isinstance(capability.status, CapabilityStatus) else str(capability.status),
            owner=capability.owner,
            created_by=capability.created_by,
            created_at=capability.created_at,
            tags=capability.tags,
            payload={
                "capability_kind": capability.capability_kind.value,
                "interface": capability.interface.model_dump(),
                "owns_durable_state": capability.owns_durable_state,
                "standing_contract": capability.standing_contract,
                "execution_mode": capability.payload.get("execution_mode", "ai_mediated"),
                **(capability.payload or {}),
            },
        )
        self._store.upsert(concept)

    def get_capability(self, capability_id: str) -> Capability | None:
        concept = self._store.get(capability_id)
        if concept is None or concept.kind != ConceptKind.CAPABILITY:
            return None
        return self._concept_to_capability(concept)

    def list_capabilities(self, capability_kind: str | None = None) -> list[Capability]:
        concepts = self._store.list_by_kind(ConceptKind.CAPABILITY)
        capabilities = [self._concept_to_capability(c) for c in concepts if isinstance(c, EnterpriseConcept)]
        if capability_kind is not None:
            capabilities = [c for c in capabilities if c.capability_kind.value == capability_kind]
        return capabilities

    def _concept_to_capability(self, concept: EnterpriseConcept) -> Capability:
        payload = concept.payload or {}
        interface_data = payload.get("interface", {})
        return Capability(
            id=concept.id,
            name=concept.name,
            description=concept.description,
            capability_kind=payload.get("capability_kind", "tool"),
            status=concept.status,
            interface=CapabilityInterface(**interface_data) if interface_data else CapabilityInterface(),
            owns_durable_state=payload.get("owns_durable_state", False),
            standing_contract=payload.get("standing_contract", False),
            tags=concept.tags,
            owner=concept.owner,
            created_by=concept.created_by,
            created_at=concept.created_at,
            payload=payload,
        )
