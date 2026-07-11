"""
Tests for handlers (skill_handler, tool_handler, workflow_handler).
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from handlers import handle_skill_step, handle_tool_step, handle_workflow_step
from models import Step, StepType, WorkflowDefinition


def _make_workflow(role: str = "developer") -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test.workflow",
        role=[role],
        steps=[Step(type="skill", name="s1", uses="architecture-review")],
    )


class TestHandleSkillStep:
    def test_skill_step_composes_prompt(self):
        """Test that a skill step composes a prompt successfully."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="review", uses="architecture-review")

        result = handle_skill_step(step, wf, {})

        assert result.status == "completed"
        assert result.composed_prompt is not None
        assert "# Role: developer" in result.composed_prompt
        assert "# Skill: architecture-review" in result.composed_prompt
        assert result.output["status"] == "ready_for_execution"

    def test_skill_step_with_role_override(self):
        """Test that role override works."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="review", uses="architecture-review")

        result = handle_skill_step(step, wf, {}, role_override="enterprise-architect")

        assert result.status == "completed"
        assert "enterprise-architect" in result.composed_prompt

    def test_skill_step_skill_not_found(self):
        """Test error when skill doesn't exist."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="bad", uses="nonexistent.skill")

        result = handle_skill_step(step, wf, {})

        assert result.status == "failed"
        assert "Cannot load skill" in result.error


class TestHandleToolStep:
    def test_tool_step_echo(self):
        """Test executing a simple echo command."""
        step = Step(
            type="tool",
            name="echo-test",
            uses="echo",
            with_={"message": "hello world"},
        )

        result = handle_tool_step(step, {})

        assert result.status == "completed"
        assert result.output["returncode"] == 0
        assert "hello world" in result.output["stdout"]

    def test_tool_step_failure(self):
        """Test handling of a failing command."""
        step = Step(
            type="tool",
            name="fail-test",
            uses="sh -c 'exit 1'",
        )

        result = handle_tool_step(step, {})

        assert result.status == "failed"
        assert result.output["returncode"] == 1

    def test_tool_step_not_allowed(self):
        """Test that commands outside the allowlist are rejected (no shell=True)."""
        step = Step(
            type="tool",
            name="not-allowed",
            uses="nonexistent_command_xyz123",
        )

        result = handle_tool_step(step, {})

        assert result.status == "failed"
        assert "not allowed" in result.error.lower()

    def test_tool_step_with_context(self):
        """Test variable substitution from context."""
        step = Step(
            type="tool",
            name="greet",
            uses="echo",
            with_={"message": "Hello ${name}!"},
        )

        result = handle_tool_step(step, {"name": "Martin"})

        assert result.status == "completed"
        assert "Hello Martin!" in result.output["stdout"]


class TestHandleWorkflowStep:
    def test_workflow_step_not_found(self):
        """Test handling when sub-workflow doesn't exist."""
        step = Step(
            type="workflow",
            name="sub-wf",
            uses="nonexistent.workflow",
        )

        result = handle_workflow_step(step, {})

        assert result.status == "failed"
        assert "not found" in result.error.lower()

    def test_workflow_step_resolves_and_loads(self):
        """Test that an existing workflow can be resolved and loaded."""
        # Create a simple sub-workflow YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "name": "sub.test",
                "kind": "workflow",
                "steps": [
                    {"type": "tool", "name": "echo-step", "uses": "echo", "with": {"message": "sub-workflow"}},
                ],
            }, f)
            sub_path = f.name

        # Create step referencing the sub-workflow by its file path
        step = Step(
            type="workflow",
            name="sub-wf",
            uses=sub_path,
        )

        result = handle_workflow_step(step, {})

        assert result.status == "completed"
        assert result.output["sub_workflow"] == sub_path
        assert len(result.output["step_results"]) == 1

        # Clean up
        Path(sub_path).unlink(missing_ok=True)
        # Clean up .wf directory that was created
        wf_dir = Path(sub_path).parent / ".wf"
        if wf_dir.exists():
            import shutil
            shutil.rmtree(wf_dir)