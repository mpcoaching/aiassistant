"""
Capability Registry service (Phase 1, contracts C2 / C7 / P1.2 / P1.3 / P1.6).

A **Capability** is an ``EnterpriseConcept`` with ``kind=capability`` whose payload
is a ``CapabilityPayload``. This module is the unified Capability Registry: one
record type for tools, skills, and the business Services (Work Session, Task
Tracking, Lead Enrichment), all of which are Capabilities in the model.

It extends the existing ``registry.py`` ``SkillRecord`` vocabulary
(``prompt | code | distilled``) by mapping to ``execution_mode``
(``ai_mediated | compiled``) and to a single ``kind: tool | skill`` type system
(anchor §10). A migration adapter ``register_from_skill_record`` loads existing
skills/tools/workflows as Capabilities without changing their callers.

Persistence is provided by ``ConceptStore`` (Postgres + strict file fallback).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from concepts import ConceptKind, ConceptStore, EnterpriseConcept, MaturationHistory


class CapabilityKind(str, Enum):
    TOOL = "tool"
    SKILL = "skill"


class ExecutionMode(str, Enum):
    AI_MEDIATED = "ai_mediated"
    COMPILED = "compiled"


class Transport(str, Enum):
    TIER2_INPROCESS = "tier2_inprocess"
    TIER3_BUS = "tier3_bus"


class Parameter(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str = ""


class AiSpec(BaseModel):
    """Present when execution_mode = ai_mediated."""

    purpose: str = ""
    inputs: List[Parameter] = Field(default_factory=list)
    outputs: List[Parameter] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    prompt_template_ref: Optional[str] = None


class CompiledRef(BaseModel):
    """Present when execution_mode = compiled."""

    module_path: str
    entrypoint: str = "run"
    tests_passed: bool = False


class CapabilityInterface(BaseModel):
    inputs: List[Parameter] = Field(default_factory=list)
    outputs: List[Parameter] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class Capability(EnterpriseConcept):
    """An EnterpriseConcept with kind=capability and a CapabilityPayload."""

    kind: ConceptKind = Field(default=ConceptKind.CAPABILITY)
    capability_kind: CapabilityKind = CapabilityKind.TOOL
    execution_mode: ExecutionMode = ExecutionMode.AI_MEDIATED
    ai_spec: Optional[AiSpec] = None
    compiled_ref: Optional[CompiledRef] = None
    transport: Transport = Transport.TIER3_BUS
    interface: CapabilityInterface = Field(default_factory=CapabilityInterface)
    owns_durable_state: bool = False
    standing_contract: bool = False


class CapabilityRegistry:
    """Single registry for all Capabilities (tools, skills, Services)."""

    def __init__(self, store: Optional[ConceptStore] = None) -> None:
        self._store = store or ConceptStore()

    # ---- authoring ----

    def register(self, capability: Capability) -> Capability:
        if capability.kind != ConceptKind.CAPABILITY:
            raise ValueError("CapabilityRegistry only registers kind=capability")
        self._store.upsert(capability)
        return capability

    def register_from_skill_record(self, rec) -> Capability:
        """Migration adapter: load an existing ``registry.SkillRecord`` as a Capability.

        Mapping (C2):
          prompt   -> execution_mode=ai_mediated
          code     -> execution_mode=compiled
          distilled -> execution_mode=compiled
          skill    -> capability_kind=skill
          tool     -> capability_kind=tool
          workflow -> exposed as capability_kind=tool (a workflow is a tool capability)
        """
        impl_to_mode = {
            "prompt": ExecutionMode.AI_MEDIATED,
            "code": ExecutionMode.COMPILED,
            "distilled": ExecutionMode.COMPILED,
        }
        kind_to_cap = {
            "skill": CapabilityKind.SKILL,
            "tool": CapabilityKind.TOOL,
            "workflow": CapabilityKind.TOOL,
        }
        mode = impl_to_mode.get(getattr(rec, "implementation", "prompt"), ExecutionMode.AI_MEDIATED)
        cap_kind = kind_to_cap.get(getattr(rec, "kind", "skill"), CapabilityKind.SKILL)
        cap = Capability(
            id=f"cap-{rec.name}",
            name=rec.name,
            description=getattr(rec, "description", None) or f"{rec.name} capability",
            owner="core",
            created_by="registry-migration",
            created_at=datetime.now(timezone.utc),
            tags=[cap_kind.value],
            capability_kind=cap_kind,
            execution_mode=mode,
            ai_spec=AiSpec(purpose=getattr(rec, "description", "") or "") if mode == ExecutionMode.AI_MEDIATED else None,
            transport=Transport.TIER3_BUS,
        )
        return self.register(cap)

    # ---- accessors ----

    def get(self, capability_id: str) -> Optional[Capability]:
        concept = self._store.get(capability_id)
        return concept if isinstance(concept, Capability) else None

    def list(self) -> List[Capability]:
        return [c for c in self._store.list_by_kind(ConceptKind.CAPABILITY) if isinstance(c, Capability)]

    def resolve(self, name: str, capability_kind: CapabilityKind) -> Optional[Capability]:
        for cap in self.list():
            if cap.name == name and cap.capability_kind == capability_kind:
                return cap
        return None

    # ---- lifecycle ----

    def record_invocation(self, capability_id: str, outcome: str = "success") -> None:
        self._store.record_invocation(capability_id, outcome)

    def promote(self, capability_id: str, compiled_ref_path: Optional[str] = None) -> Capability:
        cap = self.get(capability_id)
        if cap is None:
            raise KeyError(f"Capability not found: {capability_id}")
        cap.execution_mode = ExecutionMode.COMPILED
        if compiled_ref_path is not None:
            cap.compiled_ref = CompiledRef(module_path=compiled_ref_path, tests_passed=True)
        history = cap.payload.get("maturation_history") or {}
        history_obj = MaturationHistory(**history)
        history_obj.promoted_at = datetime.now(timezone.utc)
        cap.payload["maturation_history"] = history_obj.model_dump()
        self._store.upsert(cap)
        return cap
