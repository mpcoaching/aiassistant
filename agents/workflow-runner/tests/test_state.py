"""
Unit tests for state.py
"""

import json
import tempfile
from pathlib import Path

import pytest

from models import Step, StepType, StepResult
from state import (
    StateError,
    advance_step,
    create_workflow_state,
    fail_workflow,
    list_workflow_states,
    load_workflow_state,
)


def _make_steps() -> list:
    return [
        Step(type="skill", name="step1", uses="skill.one"),
        Step(type="tool", name="step2", uses="echo"),
    ]


class TestCreateWorkflowState:
    def test_create_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            state = create_workflow_state(
                workflow_name="test",
                workflow_path=wf_path,
                steps=_make_steps(),
            )

            assert state.workflow_name == "test"
            assert state.status == "pending"
            assert state.current_step_index == 0
            assert len(state.steps) == 2
            assert state.workflow_id is not None

            # State file should exist
            state_dir = Path(tmpdir) / ".wf"
            assert state_dir.exists()
            state_file = state_dir / f"{state.workflow_id}.json"
            assert state_file.exists()

    def test_create_with_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            state = create_workflow_state(
                workflow_name="test",
                workflow_path=wf_path,
                steps=_make_steps(),
                initial_context={"input1": "value1"},
            )

            assert state.context == {"input1": "value1"}


class TestLoadWorkflowState:
    def test_load_existing_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            created = create_workflow_state("test", wf_path, _make_steps())

            loaded = load_workflow_state(created.workflow_id, wf_path)
            assert loaded is not None
            assert loaded.workflow_id == created.workflow_id
            assert loaded.workflow_name == "test"

    def test_load_nonexistent_state(self):
        loaded = load_workflow_state("nonexistent", "/tmp/fake.yaml")
        assert loaded is None


class TestAdvanceStep:
    def test_advance_to_next_step(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            state = create_workflow_state("test", wf_path, _make_steps())

            result = StepResult(
                step_name="step1",
                step_type=StepType.SKILL,
                status="completed",
                output={"result": "ok"},
            )

            state = advance_step(state, result)
            assert state.current_step_index == 1
            assert len(state.step_results) == 1
            assert state.status == "running"

    def test_advance_to_completion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            state = create_workflow_state("test", wf_path, _make_steps())

            # Complete step 1
            state = advance_step(state, StepResult(
                step_name="step1", step_type=StepType.SKILL, status="completed"
            ))
            # Complete step 2
            state = advance_step(state, StepResult(
                step_name="step2", step_type=StepType.TOOL, status="completed"
            ))

            assert state.current_step_index == 2
            assert state.status == "completed"


class TestFailWorkflow:
    def test_fail_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            state = create_workflow_state("test", wf_path, _make_steps())

            state = fail_workflow(state, "Something went wrong")
            assert state.status == "failed"
            assert state.error == "Something went wrong"


class TestListStates:
    def test_list_states(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            create_workflow_state("test1", wf_path, _make_steps())
            create_workflow_state("test2", wf_path, _make_steps())

            states = list_workflow_states(wf_path)
            assert len(states) == 2
            assert all(s["workflow_name"] in ("test1", "test2") for s in states)

    def test_list_states_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_path = str(Path(tmpdir) / "test.yaml")
            states = list_workflow_states(wf_path)
            assert states == []