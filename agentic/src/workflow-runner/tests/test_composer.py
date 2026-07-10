"""
Unit tests for composer.py
"""

from pathlib import Path
from typing import Any, Dict

import pytest

from composer import (
    CompositionError,
    compose_skill_prompt,
    compose_tool_command,
)
from models import Step, StepType, WorkflowDefinition


def _make_workflow(role: str = "developer") -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test.workflow",
        role=[role],
        steps=[Step(type="skill", name="s1", uses="architecture-review")],
    )


class TestComposeSkillPrompt:
    def test_compose_with_role_and_skill(self):
        """Test composing a prompt with a role and skill that exist."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="review", uses="architecture-review")

        prompt = compose_skill_prompt(step, wf, {})

        # Should contain the role definition
        assert "# Role: developer" in prompt
        # Should contain the skill content
        assert "# Skill: architecture-review" in prompt
        # Should contain skill content (it's a markdown skill)
        assert "Architecture Review" in prompt or "architecture" in prompt.lower()

    def test_compose_with_role_override(self):
        """Test overriding the role."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="review", uses="architecture-review")

        prompt = compose_skill_prompt(step, wf, {}, role_override="enterprise-architect")

        assert "# Role: enterprise-architect" in prompt

    def test_compose_with_context(self):
        """Test that context is included in the prompt."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="review", uses="architecture-review")

        context = {
            "previous_output": "Some previous result",
            "user_input": "A user requirement",
        }

        prompt = compose_skill_prompt(step, wf, context)

        assert "# Workflow Context" in prompt
        assert "previous_output" in prompt
        assert "user_input" in prompt

    def test_compose_with_step_params(self):
        """Test that step parameters are included."""
        wf = _make_workflow("developer")
        step = Step(
            type="skill",
            name="review",
            uses="architecture-review",
            with_={"focus_area": "security", "depth": "detailed"},
        )

        prompt = compose_skill_prompt(step, wf, {})

        assert "# Step Parameters" in prompt
        assert "focus_area" in prompt

    def test_compose_with_outputs(self):
        """Test that expected outputs are included."""
        wf = WorkflowDefinition(
            name="test.workflow",
            role=["developer"],
            outputs=["review-report", "findings"],
            steps=[Step(type="skill", name="s1", uses="architecture-review")],
        )
        step = wf.steps[0]

        prompt = compose_skill_prompt(step, wf, {})

        assert "# Expected Outputs" in prompt
        assert "review-report" in prompt
        assert "findings" in prompt

    def test_skill_not_found(self):
        """Test error when skill file doesn't exist."""
        wf = _make_workflow("developer")
        step = Step(type="skill", name="bad", uses="nonexistent.skill.name")

        with pytest.raises(CompositionError, match="Cannot load skill"):
            compose_skill_prompt(step, wf, {})


class TestComposeToolCommand:
    def test_simple_command(self):
        step = Step(type="tool", name="echo", uses="echo")
        command = compose_tool_command(step, {})
        assert command == "echo"

    def test_command_with_params(self):
        step = Step(
            type="tool",
            name="echo",
            uses="echo",
            with_={"message": "hello world"},
        )
        command = compose_tool_command(step, {})
        assert "hello world" in command

    def test_command_with_variable_substitution(self):
        step = Step(
            type="tool",
            name="greet",
            uses="echo",
            with_={"message": "Hello ${name}!"},
        )
        command = compose_tool_command(step, {"name": "Martin"})
        assert "Hello Martin!" in command