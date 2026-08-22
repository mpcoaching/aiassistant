"""
Capability Registry service (Phase 1, contracts C2 / C7 / P1.2 / P1.3 / P1.6).

A **Capability** is defined in the People/Capability domain. This module is the
Capability Registry: it provides registration, retrieval, listing, resolution,
and domain maturation (promote). Execution metadata belongs to Operations
(CapabilityDeployment in workflow_runner).

Persistence is provided by CapabilityRepository (injected dependency).
"""

from __future__ import annotations

import builtins
from datetime import datetime, timezone
from typing import Any

from capability import Capability, CapabilityKind, CapabilityStatus
from concepts import ConceptKind  # noqa: F401 — re-exported for api.py


class CapabilityRegistry:
    """Domain catalog for Capabilities (tools, skills, Services)."""

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    # ---- authoring ----

    def register(self, capability: Capability) -> Capability:
        if self._repository is not None:
            self._repository.upsert_capability(capability)
        return capability

    def register_from_skill_record(self, rec: Any) -> Capability:
        impl_to_mode = {
            "prompt": "ai_mediated",
            "code": "compiled",
            "distilled": "compiled",
        }
        kind_to_cap = {
            "skill": CapabilityKind.SKILL,
            "tool": CapabilityKind.TOOL,
            "workflow": CapabilityKind.TOOL,
        }
        mode = impl_to_mode.get(getattr(rec, "implementation", "prompt"), "ai_mediated")
        cap_kind = kind_to_cap.get(getattr(rec, "kind", "skill"), CapabilityKind.TOOL)
        cap = Capability(
            id=f"cap-{rec.name}",
            name=rec.name,
            description=getattr(rec, "description", None) or f"{rec.name} capability",
            owner="core",
            created_by="registry-migration",
            created_at=datetime.now(timezone.utc),
            tags=[cap_kind.value],
            capability_kind=cap_kind,
            payload={"execution_mode": mode},
        )
        return self.register(cap)

    # ---- accessors ----

    def get(self, capability_id: str) -> Capability | None:
        if self._repository is None:
            return None
        return self._repository.get_capability(capability_id)

    def list(self) -> builtins.list[Capability]:
        if self._repository is None:
            return []
        return self._repository.list_capabilities()

    def list_all(self) -> builtins.list[Capability]:
        return self.list()

    def resolve(self, name: str, capability_kind: CapabilityKind) -> Capability | None:
        for cap in self.list():
            if cap.name == name and cap.capability_kind == capability_kind:
                return cap
        return None

    # ---- lifecycle ----

    def promote(self, capability_id: str) -> Capability:
        cap = self.get(capability_id)
        if cap is None:
            raise KeyError(f"Capability not found: {capability_id}")
        history = cap.payload.get("maturation_history") or {}
        history["promoted_at"] = datetime.now(timezone.utc).isoformat()
        cap.payload["maturation_history"] = history
        cap.status = CapabilityStatus.ACTIVE
        if self._repository is not None:
            self._repository.upsert_capability(cap)
        return cap
