"""
Architectural tests for Increment 31 — Capability, Skill & Tool Boundary.

Proves that:
- Capability is distinct from Skill (different classes, different responsibility)
- Skill is distinct from Tool and WorkflowDefinition
- Tool is distinct from runtime implementation (no Paperclip/MCP/LangGraph coupling)
- Capability → Skill relationship exists (Skill.capability_id)
- Skill → Tool relationship exists (Skill.tool_ids)
- Actor → Capability via CapabilityAssignment (authoritative mechanism)
- people_capability domain models do not import Paperclip/LangGraph/workflow_runner/MCP
- WorkflowDefinition does not become a synonym for Skill
- skill_ids/tool_ids on CapabilityAssignment represent authorised subset / available implementation references
"""

from __future__ import annotations

import ast
import inspect
import os

# ---- helpers ----


PEOPLE_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "people_capability", "src"
))


def _parse_source(dir_path: str) -> list[ast.Module]:
    """Parse all .py files in a directory into AST modules."""
    modules: list[ast.Module] = []
    for filename in sorted(os.listdir(dir_path)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(dir_path, filename)
        with open(path) as f:
            try:
                modules.append(ast.parse(f.read(), filename=path))
            except SyntaxError:
                continue
    return modules


# ---- A. Capability distinction from Skill ----


def test_capability_is_distinct_from_skill() -> None:
    """Capability and Skill are different domain classes with different responsibilities."""
    from capability import Capability
    from skill import Skill

    assert Capability is not Skill
    assert Capability.__name__ != Skill.__name__

    cap_fields = set(Capability.model_fields.keys())
    skill_fields = set(Skill.model_fields.keys())

    # Capability has capability_kind (itself the ability type); Skill does not
    assert "capability_kind" in cap_fields
    assert "capability_kind" not in skill_fields

    # Skill has capability_id (links to the Capability it supports); Capability does not
    assert "capability_id" in skill_fields
    assert "capability_id" not in cap_fields


def test_capability_kind_enum_not_skill_enum() -> None:
    """CapabilityKind is a categorisation of capabilities, not a Skill model reference."""
    from capability import CapabilityKind

    assert CapabilityKind.TOOL.value == "tool"
    assert CapabilityKind.SKILL.value == "skill"
    # CapabilityKind is an enum, not a reference to the Skill class
    assert not hasattr(CapabilityKind, "model_fields")


# ---- B. Skill distinction from Tool and WorkflowDefinition ----


def test_skill_is_distinct_from_tool() -> None:
    """Skill and Tool are different domain classes."""
    from skill import Skill
    from tool import Tool

    assert Skill is not Tool
    assert Skill.__name__ != Tool.__name__

    skill_fields = set(Skill.model_fields.keys())
    tool_fields = set(Tool.model_fields.keys())

    # Skill has capability_id (the Capability it supports)
    assert "capability_id" in skill_fields
    assert "capability_id" not in tool_fields

    # Tool has implementation_type and implementation_ref
    assert "implementation_type" in tool_fields
    assert "implementation_type" not in skill_fields
    assert "implementation_ref" in tool_fields
    assert "implementation_ref" not in skill_fields

    # Skill has tool_ids (the Tools it uses); Tool does not
    assert "tool_ids" in skill_fields
    assert "tool_ids" not in tool_fields


def test_skill_has_tool_ids_field() -> None:
    """Skill has a tool_ids field establishing the Skill → Tool relationship."""
    from skill import Skill

    assert "tool_ids" in Skill.model_fields


def test_workflow_definition_is_distinct_from_skill() -> None:
    """WorkflowDefinition is not a synonym for Skill — they live in different packages and serve different purposes."""
    from models import WorkflowDefinition
    from skill import Skill

    assert WorkflowDefinition.__name__ != Skill.__name__

    # WorkflowDefinition has steps (an ordered list of execution steps)
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    assert "steps" in wf_fields

    # Skill has method and capability_id, which WorkflowDefinition does not
    skill_fields = set(Skill.model_fields.keys())
    assert "method" in skill_fields
    assert "method" not in wf_fields
    assert "capability_id" in skill_fields
    assert "capability_id" not in wf_fields


def test_workflow_step_type_enums_skill_and_tool_as_invocation_targets() -> None:
    """A WorkflowDefinition's steps reference skills and tools by name — they are not the domain models themselves."""
    from models import StepType

    assert StepType.SKILL.value == "skill"
    assert StepType.TOOL.value == "tool"
    assert StepType.WORKFLOW.value == "workflow"

    # StepType is an Enum, not a reference to the Skill class
    assert not hasattr(StepType, "model_fields")


# ---- C. Tool distinction from runtime implementation ----


def test_tool_does_not_couple_to_paperclip_models() -> None:
    """Tool model describes what and how, not a concrete Paperclip tool."""
    from tool import Tool

    # Tool has implementation_type (abstract mechanism) and implementation_ref (string ref)
    fields = set(Tool.model_fields.keys())
    assert "implementation_type" in fields
    assert "implementation_ref" in fields

    # implementation_ref is a string, not a Paperclip object
    tool = Tool(id="tool-1", name="Test Tool")
    assert isinstance(tool.implementation_ref, str | None)
    assert tool.implementation_ref is None or isinstance(tool.implementation_ref, str)


def test_tool_implementation_type_does_not_embed_paperclip_logic() -> None:
    """ToolImplementationType lists mechanisms, not concrete Paperclip/MCP class references."""
    from tool import Tool, ToolImplementationType

    # The Tool model does not import or instantiate Paperclip/MCP objects
    tool = Tool(
        id="tool-api",
        name="API Tool",
        implementation_type=ToolImplementationType.HTTP_API,
        implementation_ref="https://api.example.com/v1",
    )
    assert tool.implementation_type == ToolImplementationType.HTTP_API
    assert tool.implementation_ref == "https://api.example.com/v1"
    assert isinstance(tool.implementation_ref, str)


# ---- D. Capability → Skill relationship ----


def test_skill_references_capability_via_capability_id() -> None:
    """Skill has a capability_id field linking it to the Capability it supports."""
    from skill import Skill

    skill = Skill(
        id="skill-1",
        capability_id="cap-qualify-lead",
        name="Score lead against ICP",
        method="Weighted scoring model against ideal customer profile",
    )
    assert skill.capability_id == "cap-qualify-lead"


def test_capability_does_not_require_skills() -> None:
    """A Capability can exist without any Skills referencing it — some capabilities may be directly executable."""
    from capability import Capability, CapabilityKind, CapabilityStatus

    cap = Capability(
        id="cap-direct",
        name="Direct Execution Capability",
        capability_kind=CapabilityKind.TOOL,
        status=CapabilityStatus.ACTIVE,
    )
    # Capability has no skill_ids field — it does not enumerate supporting skills
    assert not hasattr(cap, "skill_ids")


# ---- E. Skill → Tool relationship ----


def test_skill_can_reference_tools_via_tool_ids() -> None:
    """Skill has a tool_ids field that references Tools it requires or can use."""
    from skill import Skill

    skill = Skill(
        id="skill-1",
        capability_id="cap-1",
        name="Enrichment Skill",
        tool_ids=["tool-crm", "tool-email"],
    )
    assert skill.tool_ids == ["tool-crm", "tool-email"]


def test_skill_tool_ids_defaults_empty() -> None:
    """Skill.tool_ids defaults to empty list — not every skill requires tools."""
    from skill import Skill

    skill = Skill(id="skill-1", capability_id="cap-1", name="Pure Method")
    assert skill.tool_ids == []


# ---- F. Actor → Capability via CapabilityAssignment ----


def test_actor_to_capability_via_assignment() -> None:
    """CapabilityAssignment is the authoritative link between Actor and Capability."""
    from actor import Actor, ActorType
    from capability_assignment import (
        AssignmentStatus,
        AssignmentType,
        CapabilityAssignment,
    )

    actor = Actor(
        id="actor-1",
        name="Test Agent",
        actor_type=ActorType.AGENT,
        reference_id="agent-1",
    )
    assignment = CapabilityAssignment(
        id="asgn-1",
        capability_id="cap-1",
        actor_id=actor.id,
        assignment_type=AssignmentType.PRIMARY,
        status=AssignmentStatus.ACTIVE,
    )

    assert assignment.actor_id == actor.id
    assert assignment.capability_id == "cap-1"
    assert assignment.status == AssignmentStatus.ACTIVE


def test_no_actor_to_skill_direct_assignment_required() -> None:
    """Skills are available through assigned Capabilities, not via a separate Actor → Skill assignment."""
    from capability_assignment import CapabilityAssignment

    assignment = CapabilityAssignment(
        id="asgn-1",
        capability_id="cap-1",
        actor_id="actor-1",
    )

    # CapabilityAssignment has skill_ids and tool_ids as optional references,
    # but these are NOT a separate Actor → Skill assignment mechanism.
    # The primary link is capability_id.
    assert assignment.capability_id == "cap-1"
    assert hasattr(assignment, "actor_id")
    # skill_ids/tool_ids are references, not authoritative assignment links
    assert hasattr(assignment, "skill_ids")
    assert hasattr(assignment, "tool_ids")


# ---- G. skill_ids / tool_ids semantics on CapabilityAssignment ----


def test_capability_assignment_skill_ids_are_references() -> None:
    """CapabilityAssignment.skill_ids references Skill IDs — they are references, not Skill objects."""
    from capability_assignment import CapabilityAssignment

    assignment = CapabilityAssignment(
        id="asgn-1",
        capability_id="cap-1",
        actor_id="actor-1",
        skill_ids=["skill-a", "skill-b"],
        tool_ids=["tool-x"],
    )

    # skill_ids and tool_ids are lists of string IDs, not model objects
    assert all(isinstance(sid, str) for sid in assignment.skill_ids)
    assert all(isinstance(tid, str) for tid in assignment.tool_ids)


def test_capability_assignment_skill_ids_optional() -> None:
    """skill_ids and tool_ids are optional — not every capability assignment specifies which skills/tools."""
    from capability_assignment import CapabilityAssignment

    assignment = CapabilityAssignment(
        id="asgn-1",
        capability_id="cap-1",
        actor_id="actor-1",
    )
    assert assignment.skill_ids == []
    assert assignment.tool_ids == []


# ---- H. No backend leakage ----


def test_people_capability_does_not_import_paperclip() -> None:
    """people_capability domain models must not import Paperclip."""
    people_modules = _parse_source(PEOPLE_SRC)
    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "paperclip" not in alias.name.lower(), (
                        f"people_capability imports Paperclip: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "paperclip" not in node.module.lower(), (
                    f"people_capability imports from Paperclip: {node.module}"
                )


def test_people_capability_does_not_import_langgraph() -> None:
    """people_capability domain models must not import LangGraph."""
    people_modules = _parse_source(PEOPLE_SRC)
    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langgraph" not in alias.name.lower(), (
                        f"people_capability imports LangGraph: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "langgraph" not in node.module.lower(), (
                    f"people_capability imports from LangGraph: {node.module}"
                )


def test_people_capability_does_not_import_workflow_runner() -> None:
    """people_capability domain models must not import workflow_runner."""
    people_modules = _parse_source(PEOPLE_SRC)
    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "workflow_runner" not in alias.name.lower(), (
                        f"people_capability imports workflow_runner: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "workflow_runner" not in node.module.lower(), (
                    f"people_capability imports from workflow_runner: {node.module}"
                )


def test_people_capability_does_not_import_mcp() -> None:
    """people_capability domain models must not import MCP-specific implementations."""
    people_modules = _parse_source(PEOPLE_SRC)
    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "mcp" not in alias.name.lower(), (
                        f"people_capability imports MCP: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "mcp" not in node.module.lower(), (
                    f"people_capability imports from MCP: {node.module}"
                )


def test_people_capability_does_not_import_organisation() -> None:
    """people_capability domain models must not import the organisation layer."""
    people_modules = _parse_source(PEOPLE_SRC)
    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "organisation" not in alias.name.lower(), (
                        f"people_capability imports organisation: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "organisation" not in node.module.lower(), (
                    f"people_capability imports from organisation: {node.module}"
                )


# ---- I. Workflow definition distinction ----


def test_workflow_runner_models_skill_definition_is_not_domain_skill() -> None:
    """workflow_runner's SkillDefinition (prompt template) is implementation, not the domain Skill."""
    from models import SkillDefinition
    from skill import Skill

    assert SkillDefinition is not Skill

    # SkillDefinition is in workflow_runner models, not people_capability
    skill_def_fields = set(SkillDefinition.model_fields.keys())
    # SkillDefinition focuses on version/name/kind/role/intent — it's a prompt spec
    assert "version" in skill_def_fields
    assert "kind" in skill_def_fields

    # Domain Skill has capability_id and tool_ids — SkillDefinition doesn't
    domain_skill_fields = set(Skill.model_fields.keys())
    assert "capability_id" in domain_skill_fields
    assert "capability_id" not in skill_def_fields
    assert "tool_ids" in domain_skill_fields
    assert "tool_ids" not in skill_def_fields


def test_workflow_runner_models_tool_definition_is_not_domain_tool() -> None:
    """workflow_runner's ToolDefinition is implementation, not the domain Tool."""
    from models import ToolDefinition
    from tool import Tool

    assert ToolDefinition is not Tool

    tool_def_fields = set(ToolDefinition.model_fields.keys())
    assert "version" in tool_def_fields
    # ToolDefinition has action (a command template), not implementation_type
    assert "action" in tool_def_fields
    assert "action" not in set(Tool.model_fields.keys())

    # Domain Tool has implementation_type and implementation_ref
    domain_tool_fields = set(Tool.model_fields.keys())
    assert "implementation_type" in domain_tool_fields
    assert "implementation_type" not in tool_def_fields


# ---- J. CapabilityExecutionPort does not conflate concepts ----


def test_capability_execution_port_takes_capability_id_only() -> None:
    """CapabilityExecutionPort.execute takes capability_id — it does not conflate skill/tool/workflow."""
    from contracts.capability_execution import CapabilityExecutionPort

    sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(sig.parameters.keys())
    # execute(self, capability_id, context, actor_context) — no skill_id or tool_id params
    assert "capability_id" in params
    assert "skill_id" not in params
    assert "tool_id" not in params
    assert "workflow_id" not in params


def test_capability_execution_port_is_protocol_no_concrete_impl() -> None:
    """CapabilityExecutionPort is a Protocol, not a concrete implementation."""
    import typing

    from contracts.capability_execution import CapabilityExecutionPort

    assert typing.is_protocol(CapabilityExecutionPort)


# ---- K. WorkflowDefinition uses Step types, not domain Skill/Tool ----


def test_workflow_definition_step_uses_references_not_models() -> None:
    """A WorkflowDefinition Step references skills/tools by name (string 'uses'), not by domain model objects."""
    from models import Step, StepType

    step = Step(
        type=StepType.SKILL,
        name="enrich_lead",
        uses="enrich_lead_skill",
    )
    assert step.type == StepType.SKILL
    assert isinstance(step.uses, str)
    assert step.uses == "enrich_lead_skill"


# ---- L. Skill is not a workflow ----


def test_skill_is_not_workflow_definition() -> None:
    """A Skill does not need to become a WorkflowDefinition merely because it becomes repeatable."""
    from models import WorkflowDefinition
    from skill import Skill

    skill_fields = set(Skill.model_fields.keys())
    wf_fields = set(WorkflowDefinition.model_fields.keys())

    # WorkflowDefinition has steps; Skill does not
    assert "steps" in wf_fields
    assert "steps" not in skill_fields

    # Skill has method; WorkflowDefinition does not
    assert "method" in skill_fields
    assert "method" not in wf_fields
