"""
Prompt Composer — composes prompts from Role + Skill + Workflow Context.

Given a skill step, the composer:
1. Loads the role definition (if specified)
2. Loads the skill definition or markdown file
3. Loads any workflow context (previous step outputs)
4. Composes a complete prompt string
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from models import Step, WorkflowDefinition


class CompositionError(Exception):
    """Raised when prompt composition fails."""
    pass


def _read_file_content(path: Path) -> str:
    """Read a file and return its content as a string."""
    try:
        with open(path, "r") as f:
            return f.read()
    except IOError as e:
        raise CompositionError(f"Cannot read file {path}: {e}")


def _load_role_content(role_name: str, search_paths: Optional[List[Path]] = None) -> str:
    """Load a role definition file."""
    if search_paths is None:
        _repo_root = Path(__file__).resolve().parent.parent.parent.parent
        search_paths = [_repo_root / "agentic" / "docs" / "roles"]

    for base in search_paths:
        # Try <role>/role.md
        p = base / role_name / "role.md"
        if p.exists():
            return _read_file_content(p)
        # Try <role>.md
        p = base / f"{role_name}.md"
        if p.exists():
            return _read_file_content(p)

    raise CompositionError(f"Role file not found for: {role_name}")


def _load_skill_content(skill_name: str, search_paths: Optional[List[Path]] = None) -> str:
    """Load a skill definition file (markdown or YAML)."""
    if search_paths is None:
        _repo_root = Path(__file__).resolve().parent.parent.parent.parent
        search_paths = [_repo_root / "agentic" / "skills"]

    for base in search_paths:
        # Try .md
        p = base / f"{skill_name}.md"
        if p.exists():
            return _read_file_content(p)
        # Try .yaml
        p = base / f"{skill_name}.yaml"
        if p.exists():
            return _read_file_content(p)

    raise CompositionError(f"Skill file not found for: {skill_name}")


def compose_skill_prompt(
    step: Step,
    workflow: WorkflowDefinition,
    context: Dict[str, Any],
    role_override: Optional[str] = None,
) -> str:
    """
    Compose a complete prompt for a skill step.

    The prompt is composed from:
    - Role definition (if a role is specified in the workflow or step)
    - Skill definition (the actual instructions)
    - Workflow context (inputs, previous step outputs)
    - Step-specific parameters (the 'with' field)

    Args:
        step: The skill step to compose a prompt for.
        workflow: The parent workflow definition.
        context: Current workflow context (inputs, previous outputs).
        role_override: Optional role name to use instead of the workflow's role.

    Returns:
        A complete prompt string ready for execution.
    """
    parts: List[str] = []

    # 1. Role definition
    role_name = role_override or (workflow.role[0] if workflow.role else None)
    if role_name:
        try:
            role_content = _load_role_content(role_name)
            parts.append(f"# Role: {role_name}\n")
            parts.append(role_content)
            parts.append("")
        except CompositionError:
            # Role is optional — warn but continue
            parts.append(f"# Role: {role_name} (not found)")
            parts.append("")

    # 2. Skill definition
    try:
        skill_content = _load_skill_content(step.uses)
        parts.append(f"# Skill: {step.uses}\n")
        parts.append(skill_content)
        parts.append("")
    except CompositionError as e:
        raise CompositionError(f"Cannot load skill '{step.uses}': {e}")

    # 3. Workflow context
    if context:
        parts.append("# Workflow Context\n")
        for key, value in context.items():
            if isinstance(value, str):
                parts.append(f"## {key}\n{value}\n")
            else:
                import json
                parts.append(f"## {key}\n```json\n{json.dumps(value, indent=2)}\n```\n")

    # 4. Step-specific parameters
    if step.with_:
        parts.append("# Step Parameters\n")
        import json
        parts.append(f"```json\n{json.dumps(step.with_, indent=2)}\n```\n")

    # 5. Output expectations from workflow definition
    if workflow.outputs:
        parts.append("# Expected Outputs\n")
        for output in workflow.outputs:
            parts.append(f"- {output}")

    return "\n".join(parts).strip()


def compose_tool_command(
    step: Step,
    context: Dict[str, Any],
) -> str:
    """
    Compose a shell command for a tool step.

    For simple tools, the 'uses' field is the command.
    For defined tools, the action template is resolved with context variables.

    Args:
        step: The tool step to compose a command for.
        context: Current workflow context for variable substitution.

    Returns:
        A shell command string.
    """
    # Simple case: uses is the command directly
    command = step.uses

    # If there are step parameters, append them as arguments
    if step.with_:
        for key, value in step.with_.items():
            if isinstance(value, str):
                # Simple variable substitution
                resolved = value
                for ctx_key, ctx_val in context.items():
                    if isinstance(ctx_val, str):
                        resolved = resolved.replace(f"${{{ctx_key}}}", ctx_val)
                command += f" {resolved}"
            else:
                command += f" {value}"

    return command