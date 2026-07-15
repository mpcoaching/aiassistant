"""
Unit tests for loader.py
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from loader import (
    WorkflowLoadError,
    _normalize_step,
    load_workflow,
    resolve_skill_path,
    resolve_tool_path,
    resolve_workflow_path,
)
from models import StepType


class TestNormalizeStep:
    def test_plain_string(self):
        step = _normalize_step("my.skill")
        assert step is not None
        assert step.type == StepType.SKILL
        assert step.name == "my.skill"
        assert step.uses == "my.skill"

    def test_canonical_format(self):
        step = _normalize_step({
            "type": "tool",
            "name": "echo-test",
            "uses": "echo",
            "with": {"message": "hello"},
        })
        assert step is not None
        assert step.type == StepType.TOOL
        assert step.name == "echo-test"
        assert step.uses == "echo"
        assert step.with_ == {"message": "hello"}

    def test_capability_format(self):
        step = _normalize_step({"capability": "my.skill"})
        assert step is not None
        assert step.type == StepType.SKILL
        assert step.uses == "my.skill"

    def test_capability_dict_format(self):
        step = _normalize_step({"capability": {"name": "my.skill"}})
        assert step is not None
        assert step.type == StepType.SKILL
        assert step.uses == "my.skill"

    def test_workflow_key_format(self):
        step = _normalize_step({"workflow": "sub.workflow"})
        assert step is not None
        assert step.type == StepType.WORKFLOW
        assert step.uses == "sub.workflow"

    def test_tool_key_format(self):
        step = _normalize_step({"tool": "my.tool"})
        assert step is not None
        assert step.type == StepType.TOOL
        assert step.uses == "my.tool"

    def test_skill_key_format(self):
        step = _normalize_step({"skill": "my.skill"})
        assert step is not None
        assert step.type == StepType.SKILL
        assert step.uses == "my.skill"

    def test_invalid_format(self):
        step = _normalize_step(42)
        assert step is None

    def test_empty_dict(self):
        step = _normalize_step({})
        assert step is None


class TestLoadWorkflow:
    def test_load_canonical_yaml(self):
        """Test loading a workflow in the canonical format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "name": "test.workflow",
                "description": "A test workflow",
                "kind": "workflow",
                "role": ["developer"],
                "inputs": ["input1"],
                "outputs": ["output1"],
                "steps": [
                    {"type": "skill", "name": "step1", "uses": "skill.one"},
                    {"type": "tool", "name": "step2", "uses": "echo"},
                ],
            }, f)
            fpath = f.name

        try:
            wf = load_workflow(fpath)
            assert wf.name == "test.workflow"
            assert wf.description == "A test workflow"
            assert wf.role == ["developer"]
            assert len(wf.steps) == 2
            assert wf.steps[0].type == StepType.SKILL
            assert wf.steps[1].type == StepType.TOOL
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_load_with_workflow_wrapper(self):
        """Test loading a workflow with the 'workflow:' top-level wrapper."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflow": {
                    "name": "wrapped.workflow",
                    "steps": [
                        {"type": "skill", "name": "s1", "uses": "skill.one"},
                    ],
                }
            }, f)
            fpath = f.name

        try:
            wf = load_workflow(fpath)
            assert wf.name == "wrapped.workflow"
            assert len(wf.steps) == 1
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_load_with_execution_format(self):
        """Test loading a workflow with the old 'execution:' format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "name": "old.format",
                "execution": [
                    "skill.one",
                    "skill.two",
                ],
            }, f)
            fpath = f.name

        try:
            wf = load_workflow(fpath)
            assert wf.name == "old.format"
            assert len(wf.steps) == 2
            assert all(s.type == StepType.SKILL for s in wf.steps)
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_load_with_capability_format(self):
        """Test loading a workflow with the 'capability:' step format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "name": "cap.format",
                "steps": [
                    {"capability": "skill.one"},
                    {"capability": {"name": "skill.two"}},
                ],
            }, f)
            fpath = f.name

        try:
            wf = load_workflow(fpath)
            assert wf.name == "cap.format"
            assert len(wf.steps) == 2
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_file_not_found(self):
        with pytest.raises(WorkflowLoadError, match="not found"):
            load_workflow("/nonexistent/path.yaml")

    def test_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{{invalid: yaml: broken")
            fpath = f.name

        try:
            with pytest.raises(WorkflowLoadError, match="Invalid YAML"):
                load_workflow(fpath)
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_missing_name(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"steps": [{"type": "skill", "name": "s1", "uses": "s1"}]}, f)
            fpath = f.name

        try:
            with pytest.raises(WorkflowLoadError, match="must have a 'name' field"):
                load_workflow(fpath)
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_missing_steps(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"name": "test"}, f)
            fpath = f.name

        try:
            with pytest.raises(WorkflowLoadError, match="no steps"):
                load_workflow(fpath)
        finally:
            Path(fpath).unlink(missing_ok=True)


class TestResolvePaths:
    def test_resolve_skill_path_found(self):
        # The skills directory exists with real files
        path = resolve_skill_path("architecture-review")
        assert path is not None
        assert path.exists()

    def test_resolve_skill_path_not_found(self):
        path = resolve_skill_path("nonexistent.skill")
        assert path is None

    def test_resolve_workflow_path_found(self):
        path = resolve_workflow_path("architecture.solution.create")
        assert path is not None
        assert path.exists()

    def test_resolve_workflow_path_not_found(self):
        path = resolve_workflow_path("nonexistent.workflow")
        assert path is None