"""
Tests for the Registry (skill/tool/workflow catalog and resolution).

TDD: these tests are written before registry.py exists; they define the
behaviour the implementation must satisfy (see ai-orchestration-design.md).
"""

import json
from pathlib import Path

import pytest

from registry import Registry, SkillRecord


def _write(path: Path, text: str = "# skill\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestSkillRecord:
    def test_requires_non_empty_name(self):
        with pytest.raises(ValueError):
            SkillRecord(name="", kind="skill")

    def test_rejects_invalid_kind(self):
        with pytest.raises(ValueError):
            SkillRecord(name="x", kind="bogus")

    def test_rejects_invalid_implementation_tier(self):
        with pytest.raises(ValueError):
            SkillRecord(name="x", kind="skill", implementation="magic")


class TestScan:
    def test_lists_skills_from_dir(self, tmp_path):
        skills = tmp_path / "skills"
        _write(skills / "alpha.md")
        _write(skills / "beta.yaml")

        reg = Registry(skills, tmp_path / "tools", tmp_path / "wf")

        names = {s.name for s in reg.list_skills()}
        assert names == {"alpha", "beta"}

    def test_lists_tools_and_workflows(self, tmp_path):
        tools = tmp_path / "tools"
        wf = tmp_path / "wf"
        _write(tools / "t1.yaml")
        _write(wf / "w1.yaml")

        reg = Registry(tmp_path / "skills", tools, wf)

        assert {t.name for t in reg.list_tools()} == {"t1"}
        assert {w.name for w in reg.list_workflows()} == {"w1"}

    def test_missing_dirs_do_not_error(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        assert reg.list_skills() == []


class TestGet:
    def test_get_skill_returns_record(self, tmp_path):
        _write(tmp_path / "skills" / "alpha.md")
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        rec = reg.get_skill("alpha")
        assert rec.name == "alpha"
        assert rec.kind == "skill"
        assert rec.spec_path.endswith("alpha.md")

    def test_get_missing_skill_raises(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(KeyError):
            reg.get_skill("nope")

    def test_get_tool_and_workflow(self, tmp_path):
        tools = tmp_path / "tools"
        wf = tmp_path / "wf"
        _write(tools / "t1.yaml")
        _write(wf / "w1.yaml")
        reg = Registry(tmp_path / "skills", tools, wf)

        assert reg.get_tool("t1").kind == "tool"
        assert reg.get_workflow("w1").kind == "workflow"

    def test_get_missing_tool_raises(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(KeyError):
            reg.get_tool("nope")


class TestRegisterSkill:
    def test_register_writes_spec_and_records(self, tmp_path):
        skills = tmp_path / "skills"
        reg = Registry(skills, tmp_path / "tools", tmp_path / "wf")

        rec = reg.register_skill("gamma", description="does a thing", spec="# Gamma\n")

        assert (skills / "gamma.md").exists()
        assert reg.get_skill("gamma").name == "gamma"
        assert rec.description == "does a thing"

    def test_register_requires_name(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(ValueError):
            reg.register_skill("")

    def test_register_rejects_non_skill_kind(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(ValueError):
            reg.register_skill("x", kind="tool")


class TestSetImplementation:
    def test_sets_tier_and_module_path(self, tmp_path):
        _write(tmp_path / "skills" / "alpha.md")
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")

        rec = reg.set_implementation("alpha", "code", "/compiled/alpha.py")

        assert rec.implementation == "code"
        assert rec.module_path == "/compiled/alpha.py"

    def test_rejects_invalid_tier(self, tmp_path):
        _write(tmp_path / "skills" / "alpha.md")
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(ValueError):
            reg.set_implementation("alpha", "bogus")

    def test_raises_for_unknown_skill(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(KeyError):
            reg.set_implementation("ghost", "code")


class TestResolve:
    def test_resolve_returns_spec_path(self, tmp_path):
        _write(tmp_path / "skills" / "alpha.md")
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        assert reg.resolve("alpha", "skill") == Path(tmp_path / "skills" / "alpha.md")

    def test_resolve_unknown_returns_none(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        assert reg.resolve("ghost", "skill") is None

    def test_resolve_rejects_invalid_kind(self, tmp_path):
        reg = Registry(tmp_path / "skills", tmp_path / "tools", tmp_path / "wf")
        with pytest.raises(ValueError):
            reg.resolve("alpha", "bogus")


class TestManifest:
    def test_manifest_persists_implementation_tier(self, tmp_path):
        skills = tmp_path / "skills"
        _write(skills / "alpha.md")
        manifest = tmp_path / "manifest.json"
        reg = Registry(skills, tmp_path / "tools", tmp_path / "wf", manifest_path=manifest)
        reg.set_implementation("alpha", "code", "/compiled/alpha.py")

        # New registry instance reloads from manifest.
        reg2 = Registry(skills, tmp_path / "tools", tmp_path / "wf", manifest_path=manifest)
        rec = reg2.get_skill("alpha")
        assert rec.implementation == "code"
        assert rec.module_path == "/compiled/alpha.py"

    def test_manifest_is_valid_json(self, tmp_path):
        skills = tmp_path / "skills"
        _write(skills / "alpha.md")
        manifest = tmp_path / "manifest.json"
        reg = Registry(skills, tmp_path / "tools", tmp_path / "wf", manifest_path=manifest)
        reg.register_skill("alpha")
        data = json.loads(manifest.read_text())
        assert "records" in data
