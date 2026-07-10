"""
Unit tests for models.py
"""

import pytest
from pydantic import ValidationError

from models import Step, StepType, WorkflowDefinition, WorkflowState, StepResult


class TestStep:
    def test_canonical_step(self):
        step = Step(type="skill", name="test-skill", uses="my.skill")
        assert step.type == StepType.SKILL
        assert step.name == "test-skill"
        assert step.uses == "my.skill"

    def test_step_with_params(self):
        step = Step(
            type="tool",
            name="test-tool",
            uses="echo",
            with_={"message": "hello"},
        )
        assert step.type == StepType.TOOL
        assert step.with_ == {"message": "hello"}

    def test_step_with_alias_with(self):
        step = Step(type="skill", name="test", uses="test", **{"with": {"key": "val"}})
        assert step.with_ == {"key": "val"}

    def test_invalid_step_type(self):
        with pytest.raises(ValidationError):
            Step(type="invalid", name="test", uses="test")


class TestWorkflowDefinition:
    def test_minimal_workflow(self):
        wf = WorkflowDefinition(
            name="test.workflow",
            steps=[
                Step(type="skill", name="step1", uses="skill.one"),
            ],
        )
        assert wf.name == "test.workflow"
        assert wf.version == "1"
        assert len(wf.steps) == 1

    def test_workflow_with_all_fields(self):
        wf = WorkflowDefinition(
            version="2",
            name="full.workflow",
            description="A full workflow",
            kind="workflow",
            role=["developer"],
            intent={"outcome": "test"},
            inputs=["input1"],
            outputs=["output1"],
            steps=[
                Step(type="skill", name="s1", uses="skill.one"),
                Step(type="tool", name="t1", uses="echo"),
                Step(type="workflow", name="w1", uses="sub.workflow"),
            ],
        )
        assert wf.version == "2"
        assert len(wf.steps) == 3

    def test_empty_steps_raises_error(self):
        with pytest.raises(ValidationError):
            WorkflowDefinition(name="empty", steps=[])

    def test_invalid_kind(self):
        with pytest.raises(ValidationError):
            WorkflowDefinition(
                name="test",
                kind="invalid",
                steps=[Step(type="skill", name="s1", uses="s1")],
            )


class TestWorkflowState:
    def test_create_state(self):
        state = WorkflowState(
            workflow_id="abc123",
            workflow_name="test",
            workflow_path="/path/to/workflow.yaml",
            steps=[Step(type="skill", name="s1", uses="s1")],
        )
        assert state.status == "pending"
        assert state.current_step_index == 0

    def test_state_status_validation(self):
        with pytest.raises(ValidationError):
            WorkflowState(
                workflow_id="abc",
                workflow_name="test",
                workflow_path="/path",
                status="invalid",
                steps=[Step(type="skill", name="s1", uses="s1")],
            )


class TestStepResult:
    def test_create_result(self):
        result = StepResult(
            step_name="test-step",
            step_type=StepType.SKILL,
        )
        assert result.status == "pending"
        assert result.duration_seconds is None

    def test_completed_result(self):
        result = StepResult(
            step_name="test-step",
            step_type=StepType.TOOL,
            status="completed",
            output={"key": "value"},
            duration_seconds=1.5,
        )
        assert result.status == "completed"
        assert result.output == {"key": "value"}