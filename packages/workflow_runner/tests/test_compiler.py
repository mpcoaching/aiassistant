"""
Tests for the Compiler (promotes a prompt skill to a reusable code module).

TDD: written before compiler.py exists. See ai-orchestration-design.md,
Tier 1 wrapper codegen. The generated module is loaded dynamically and its
wiring verified without depending on the LLM runtime or composer.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from compiler import compile_skill


def _make_skill(tmp_path: Path, name: str = "alpha") -> "Registry":  # noqa: F821
    from registry import Registry

    skills = tmp_path / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / f"{name}.md").write_text(f"# Skill: {name}\n")
    return Registry(skills, tmp_path / "tools", tmp_path / "wf")


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("gen_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCompileSkill:
    def test_generates_module_file(self, tmp_path):
        reg = _make_skill(tmp_path)
        path = compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")

        assert path.exists()
        assert path.suffix == ".py"
        text = path.read_text()
        assert "def run" in text
        assert "run_skill" in text
        assert "'alpha'" in text or '"alpha"' in text

    def test_sets_registry_tier_and_module_path(self, tmp_path):
        reg = _make_skill(tmp_path)
        path = compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")

        rec = reg.get_skill("alpha")
        assert rec.implementation == "code"
        assert rec.module_path == str(path)

    def test_is_idempotent(self, tmp_path):
        reg = _make_skill(tmp_path)
        first = compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")
        second = compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")
        assert first == second

    def test_unknown_skill_raises(self, tmp_path):
        reg = _make_skill(tmp_path)
        with pytest.raises(KeyError):
            compile_skill(reg, "ghost", compiled_dir=tmp_path / "_compiled")

    def test_generated_module_is_wired_to_run_skill(self, tmp_path):
        reg = _make_skill(tmp_path)
        path = compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")

        module = _load_module(path)
        captured = {}
        module.run_skill = lambda name, ctx, **kw: captured.update(name=name, ctx=ctx) or {"status": "completed"}
        result = module.run({"x": 1})

        assert result == {"status": "completed"}
        assert captured["name"] == "alpha"
        assert captured["ctx"] == {"x": 1}

    def test_default_compiled_dir_next_to_spec(self, tmp_path):
        reg = _make_skill(tmp_path)
        path = compile_skill(reg, "alpha")  # no compiled_dir -> _compiled sibling

        assert path.parent.name == "_compiled"
        assert path.exists()

    def test_persists_tier_in_manifest(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        (skills / "alpha.md").write_text("# Skill: alpha\n")
        manifest = tmp_path / "manifest.json"
        from registry import Registry

        reg = Registry(skills, tmp_path / "tools", tmp_path / "wf", manifest_path=manifest)
        compile_skill(reg, "alpha", compiled_dir=tmp_path / "_compiled")

        data = json.loads(manifest.read_text())
        alpha = next(r for r in data["records"] if r["name"] == "alpha")
        assert alpha["implementation"] == "code"
        assert alpha["module_path"].endswith(".py")
