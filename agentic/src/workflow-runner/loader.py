"""
Workflow Loader — load and validate workflow YAML files.

Supports multiple YAML formats for backward compatibility:
1. Canonical format (workflow-schema.md): uses 'steps' with 'type', 'name', 'uses'
2. Old format A: uses 'steps' with 'capability' entries
3. Old format B: uses 'execution' with plain skill name lists

All formats are normalized to the canonical WorkflowDefinition model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from models import (
    SkillDefinition,
    Step,
    StepType,
    ToolDefinition,
    WorkflowDefinition,
)


class WorkflowLoadError(Exception):
    """Raised when a workflow cannot be loaded or validated."""
    pass


def _normalize_step(step_data: Any) -> Optional[Step]:
    """Normalize a single step from any supported format to a canonical Step."""
    if isinstance(step_data, str):
        # Plain string: treat as a skill name
        return Step(type=StepType.SKILL, name=step_data, uses=step_data)

    if isinstance(step_data, dict):
        # Format 1: Canonical {"type": "skill", "name": "...", "uses": "...", "with": {...}}
        if "type" in step_data:
            step_type = StepType(step_data["type"])
            name = step_data.get("name", step_data.get("uses", "unnamed"))
            uses = step_data.get("uses", name)
            with_params = step_data.get("with")
            return Step(type=step_type, name=name, uses=uses, with_=with_params)

        # Format 2: {"capability": "skill.name"} or {"capability": {"name": "skill.name"}}
        if "capability" in step_data:
            cap = step_data["capability"]
            if isinstance(cap, dict):
                name = cap.get("name", "unnamed")
            else:
                name = str(cap)
            return Step(type=StepType.SKILL, name=name, uses=name)

        # Format 3: {"workflow": "workflow.name"} or {"tool": "tool.name"}
        for key in ("workflow", "skill", "tool"):
            if key in step_data:
                val = step_data[key]
                if isinstance(val, dict):
                    name = val.get("name", "unnamed")
                else:
                    name = str(val)
                return Step(type=StepType(key), name=name, uses=name)

    return None


def _load_definition_file(path: Path) -> Optional[Union[SkillDefinition, ToolDefinition]]:
    """Load a referenced skill or tool definition from a file."""
    if not path.exists():
        return None

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, IOError):
        return None

    if not isinstance(data, dict):
        return None

    kind = data.get("kind")
    if kind == "skill":
        return SkillDefinition(**data)
    elif kind == "tool":
        return ToolDefinition(**data)

    return None


def load_workflow(
    path: Union[str, Path],
    search_paths: Optional[List[Path]] = None,
) -> WorkflowDefinition:
    """
    Load a workflow YAML file and return a canonical WorkflowDefinition.

    Args:
        path: Path to the workflow YAML file.
        search_paths: Additional directories to search for referenced skills/tools/workflows.

    Returns:
        A validated WorkflowDefinition.

    Raises:
        WorkflowLoadError: If the file cannot be loaded or validated.
    """
    filepath = Path(path)

    if not filepath.exists():
        raise WorkflowLoadError(f"Workflow file not found: {path}")

    try:
        with open(filepath, "r") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise WorkflowLoadError(f"Invalid YAML in {path}: {e}")

    if not isinstance(raw, dict):
        raise WorkflowLoadError(f"Workflow file must contain a mapping, got {type(raw).__name__}")

    # Normalise: handle both top-level "workflow:" wrapper and flat format
    data = raw.get("workflow", raw)

    # Extract name
    name = data.get("name")
    if not name:
        raise WorkflowLoadError("Workflow must have a 'name' field")

    description = data.get("description")
    kind = data.get("kind", "workflow")
    role = data.get("role")
    intent = data.get("intent")
    inputs = data.get("inputs")
    outputs = data.get("outputs")
    version = data.get("version", "1")

    # Normalise steps from any supported format
    raw_steps = data.get("steps") or data.get("execution") or []
    if not raw_steps:
        raise WorkflowLoadError(f"Workflow '{name}' has no steps or execution section")

    steps: List[Step] = []
    for raw_step in raw_steps:
        normalized = _normalize_step(raw_step)
        if normalized is None:
            raise WorkflowLoadError(
                f"Workflow '{name}': cannot parse step: {raw_step}"
            )
        steps.append(normalized)

    return WorkflowDefinition(
        version=version,
        name=name,
        description=description,
        kind=kind,
        role=role,
        intent=intent,
        inputs=inputs,
        outputs=outputs,
        steps=steps,
    )


def resolve_skill_path(skill_name: str, search_paths: Optional[List[Path]] = None) -> Optional[Path]:
    """
    Resolve a skill name to a file path.

    Searches for:
    - <skill_name>.md (markdown skill file)
    - <skill_name>.yaml or <skill_name>.yml (YAML skill definition)
    - <skill_name>/ (directory with index or matching files)
    """
    if search_paths is None:
        search_paths = [
            Path("agentic/skills"),
            Path("agentic/docs/skills"),
        ]

    for base in search_paths:
        # Try .md
        p = base / f"{skill_name}.md"
        if p.exists():
            return p
        # Try .yaml
        p = base / f"{skill_name}.yaml"
        if p.exists():
            return p
        # Try .yml
        p = base / f"{skill_name}.yml"
        if p.exists():
            return p

    return None


def resolve_tool_path(tool_name: str, search_paths: Optional[List[Path]] = None) -> Optional[Path]:
    """
    Resolve a tool name to a file path.
    """
    if search_paths is None:
        search_paths = [
            Path("agentic/tools"),
        ]

    for base in search_paths:
        p = base / f"{tool_name}.yaml"
        if p.exists():
            return p
        p = base / f"{tool_name}.yml"
        if p.exists():
            return p

    return None


def resolve_workflow_path(workflow_name: str, search_paths: Optional[List[Path]] = None) -> Optional[Path]:
    """
    Resolve a workflow name to a file path.
    """
    if search_paths is None:
        search_paths = [
            Path("agentic/docs/workflows"),
            Path("agentic/workflows"),
        ]

    for base in search_paths:
        p = base / f"{workflow_name}.yaml"
        if p.exists():
            return p
        p = base / f"{workflow_name}.yml"
        if p.exists():
            return p

    return None