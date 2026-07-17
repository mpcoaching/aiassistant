"""
TDD tests for the Capability Registry service (Phase 1, contracts C2 / P1.2 / P1.3).

Behaviour (SA-CONTRACTS-PHASE1.md C2, C7):
- A Capability is an EnterpriseConcept with kind=capability and a CapabilityPayload
  (capability_kind: tool|skill, execution_mode: ai_mediated|compiled,
  ai_spec/compiled_ref, maturation_history, owns_durable_state, standing_contract).
- register / get / resolve(name, capability_kind) / list / record_invocation / promote
- Strict persistence: write failure raises (RUNTIME-MAPPING.md Registry Strictness).
- Migration adapter: existing SkillRecord (prompt|code|distilled) loads as a
  Capability with execution_mode mapped (prompt->ai_mediated, code/distilled->compiled).
- The three business Services register as Capabilities (owns_durable_state=true).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from capabilities import (
    AiSpec,
    Capability,
    CapabilityInterface,
    CapabilityKind,
    ExecutionMode,
    Parameter,
    CapabilityRegistry,
)
from concepts import ConceptKind, ConceptStore, EnterpriseConcept


def _ai_spec() -> AiSpec:
    return AiSpec(
        purpose="do a thing",
        inputs=[Parameter(name="x", type="string", required=True, description="x")],
        outputs=[Parameter(name="y", type="string", required=True, description="y")],
        constraints=[],
    )


def _capability(name: str, kind: CapabilityKind = CapabilityKind.TOOL, **kw) -> Capability:
    return Capability(
        id=kw.pop("id", f"cap-{name}"),
        name=name,
        description=kw.pop("description", f"{name} capability"),
        owner=kw.pop("owner", "core"),
        created_by=kw.pop("created_by", "assistant_reasoning"),
        created_at=kw.pop("created_at", datetime(2026, 7, 16, tzinfo=timezone.utc)),
        tags=kw.pop("tags", ["tool"]),
        capability_kind=kind,
        execution_mode=kw.pop("execution_mode", "ai_mediated"),
        ai_spec=kw.pop("ai_spec", _ai_spec()),
        compiled_ref=kw.pop("compiled_ref", None),
        transport=kw.pop("transport", "tier3_bus"),
        interface=kw.pop(
            "interface",
            CapabilityInterface(
                inputs=[Parameter(name="x", type="string", required=True, description="x")],
                outputs=[Parameter(name="y", type="string", required=True, description="y")],
                errors=["error"],
            ),
        ),
        owns_durable_state=kw.pop("owns_durable_state", False),
        standing_contract=kw.pop("standing_contract", False),
    )


# ---- register / get / resolve ----------------------------------------------

def test_register_and_get(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    cap = _capability("work_session", owns_durable_state=True, standing_contract=True)
    reg.register(cap)
    got = reg.get(cap.id)
    assert got is not None
    assert got.name == "work_session"
    assert got.owns_durable_state is True


def test_resolve_by_name_and_kind(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    reg.register(_capability("enrich", kind=CapabilityKind.TOOL))
    reg.register(_capability("summarise", kind=CapabilityKind.SKILL))
    resolved = reg.resolve("enrich", CapabilityKind.TOOL)
    assert resolved is not None
    assert resolved.name == "enrich"
    # wrong kind -> not found
    assert reg.resolve("enrich", CapabilityKind.SKILL) is None


def test_resolve_missing_returns_none(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    assert reg.resolve("nope", CapabilityKind.TOOL) is None


def test_list_capabilities(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    reg.register(_capability("a"))
    reg.register(_capability("b"))
    assert {c.name for c in reg.list()} == {"a", "b"}


# ---- strict persistence ------------------------------------------------------

def test_register_strict_persistence_raises(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    tmp_path.chmod(0o000)
    try:
        with pytest.raises(OSError):
            reg.register(_capability("x"))
    finally:
        tmp_path.chmod(0o755)


# ---- maturation / promotion (C2) -------------------------------------------

def test_record_invocation_updates_maturation(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    cap = _capability("y")
    reg.register(cap)
    reg.record_invocation(cap.id, "success")
    reg.record_invocation(cap.id, "success")
    reg.record_invocation(cap.id, "failure")
    got = reg.get(cap.id)
    assert got.payload["maturation_history"]["invocation_count"] == 3
    assert got.payload["maturation_history"]["correction_count"] == 1


def test_promote_sets_compiled(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    cap = _capability("z", execution_mode="ai_mediated")
    reg.register(cap)
    reg.promote(cap.id, compiled_ref_path="agentic/skills/_compiled/z.py")
    got = reg.get(cap.id)
    assert got.execution_mode == "compiled"
    assert got.compiled_ref is not None
    assert got.compiled_ref.module_path == "agentic/skills/_compiled/z.py"


# ---- SkillRecord -> Capability migration (P1.3 / C2) -----------------------

def test_skillrecord_maps_to_capability(tmp_path: Path) -> None:
    # Mirror registry.SkillRecord shape (prompt|code|distilled tiers)
    from registry import SkillRecord

    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    prompt_rec = SkillRecord(name="draft_idea", kind="skill", implementation="prompt")
    code_rec = SkillRecord(name="run_test", kind="tool", implementation="code")
    distilled_rec = SkillRecord(name="pci_sop", kind="workflow", implementation="distilled")

    cap_prompt = reg.register_from_skill_record(prompt_rec)
    cap_code = reg.register_from_skill_record(code_rec)
    cap_distilled = reg.register_from_skill_record(distilled_rec)

    # prompt -> ai_mediated; code/distilled -> compiled
    assert cap_prompt.execution_mode == "ai_mediated"
    assert cap_code.execution_mode == "compiled"
    assert cap_distilled.execution_mode == "compiled"
    # kind mapping: skill->skill, tool->tool, workflow->tool (a workflow is exposed as a tool capability)
    assert cap_prompt.capability_kind == "skill"
    assert cap_code.capability_kind == "tool"
    assert cap_distilled.capability_kind == "tool"
    # registered and resolvable
    assert reg.resolve("draft_idea", "skill") is not None


# ---- three business services register as capabilities (C7 / P1.6) ----------

def test_business_services_register_as_capabilities(tmp_path: Path) -> None:
    reg = CapabilityRegistry(ConceptStore(data_dir=str(tmp_path)))
    for name in ("work_session", "task_tracking", "lead_enrichment"):
        cap = _capability(name, owns_durable_state=True, standing_contract=True)
        reg.register(cap)
    for name in ("work_session", "task_tracking", "lead_enrichment"):
        got = reg.resolve(name, "tool")
        assert got is not None
        assert got.owns_durable_state is True
        assert got.standing_contract is True
