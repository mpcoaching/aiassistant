"""
Registry — the catalog of skills, tools, and workflows.

Responsibilities:
- Discover artifacts on the filesystem (agentic/skills, agentic/tools,
  agentic/docs/workflows).
- Resolve a name to an artifact and track each skill's `implementation` tier
  (prompt | code | distilled) and compiled module path.
- Persist catalog metadata to an optional manifest for fast lookup and to
  survive tier promotions performed by the Compiler.

This is the single source of truth the MCP authoring surface, the Choreographer,
and skill workers all read from. See ai-orchestration-design.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


IMPLEMENTATION_TIERS = ("prompt", "code", "distilled")
KINDS = ("skill", "tool", "workflow")
_SKILL_EXTS = (".md", ".yaml", ".yml")
_DEF_EXTS = (".yaml", ".yml")


@dataclass
class SkillRecord:
    """A catalog entry for a skill, tool, or workflow."""

    name: str
    kind: str
    description: Optional[str] = None
    implementation: str = "prompt"
    spec_path: Optional[str] = None
    module_path: Optional[str] = None
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None
    version: str = "1"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name is required")
        if self.kind not in KINDS:
            raise ValueError(f"Invalid kind: {self.kind}")
        if self.implementation not in IMPLEMENTATION_TIERS:
            raise ValueError(f"Invalid implementation tier: {self.implementation}")


class Registry:
    """Filesystem-backed catalog of skills, tools, and workflows."""

    def __init__(
        self,
        skills_dir: str,
        tools_dir: str,
        workflows_dir: str,
        manifest_path: Optional[str] = None,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.tools_dir = Path(tools_dir)
        self.workflows_dir = Path(workflows_dir)
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self._skills: Dict[str, SkillRecord] = {}
        self._tools: Dict[str, SkillRecord] = {}
        self._workflows: Dict[str, SkillRecord] = {}
        self._load_manifest()
        self.scan()

    # ---- Discovery ----

    def scan(self) -> None:
        """(Re)discover artifacts on the filesystem, preserving tier metadata."""
        for path in self._iter(self.skills_dir, _SKILL_EXTS):
            self._upsert(self._skills, "skill", path)
        for path in self._iter(self.tools_dir, _DEF_EXTS):
            self._upsert(self._tools, "tool", path)
        for path in self._iter(self.workflows_dir, _DEF_EXTS):
            self._upsert(self._workflows, "workflow", path)

    @staticmethod
    def _iter(directory: Path, exts) -> List[Path]:
        directory = Path(directory)
        if not directory.exists():
            return []
        found: List[Path] = []
        for ext in exts:
            found.extend(sorted(directory.glob(f"*{ext}")))
        return found

    def _upsert(self, table: Dict[str, SkillRecord], kind: str, path: Path) -> None:
        name = path.stem
        existing = table.get(name)
        if existing is not None:
            existing.spec_path = str(path)
        else:
            table[name] = SkillRecord(name=name, kind=kind, spec_path=str(path))

    # ---- Accessors ----

    def list_skills(self) -> List[SkillRecord]:
        return list(self._skills.values())

    def list_tools(self) -> List[SkillRecord]:
        return list(self._tools.values())

    def list_workflows(self) -> List[SkillRecord]:
        return list(self._workflows.values())

    def get_skill(self, name: str) -> SkillRecord:
        rec = self._skills.get(name)
        if rec is None:
            raise KeyError(f"Skill not found: {name}")
        return rec

    def get_tool(self, name: str) -> SkillRecord:
        rec = self._tools.get(name)
        if rec is None:
            raise KeyError(f"Tool not found: {name}")
        return rec

    def get_workflow(self, name: str) -> SkillRecord:
        rec = self._workflows.get(name)
        if rec is None:
            raise KeyError(f"Workflow not found: {name}")
        return rec

    # ---- Authoring ----

    def register_skill(
        self,
        name: str,
        description: Optional[str] = None,
        spec: Optional[str] = None,
        kind: str = "skill",
    ) -> SkillRecord:
        if not name:
            raise ValueError("name is required")
        if kind != "skill":
            raise ValueError("register_skill only registers skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        path = self.skills_dir / f"{name}.md"
        path.write_text(spec or f"# Skill: {name}\n\n{description or ''}\n")
        rec = SkillRecord(name=name, kind="skill", description=description, spec_path=str(path))
        self._skills[name] = rec
        self._save_manifest()
        return rec

    def set_implementation(
        self,
        name: str,
        tier: str,
        module_path: Optional[str] = None,
    ) -> SkillRecord:
        if tier not in IMPLEMENTATION_TIERS:
            raise ValueError(f"Invalid implementation tier: {tier}")
        rec = self._skills.get(name)
        if rec is None:
            raise KeyError(f"Skill not found: {name}")
        rec.implementation = tier
        if module_path is not None:
            rec.module_path = str(module_path)
        self._skills[name] = rec
        self._save_manifest()
        return rec

    def resolve(self, name: str, kind: str) -> Optional[Path]:
        table = {"skill": self._skills, "tool": self._tools, "workflow": self._workflows}.get(kind)
        if table is None:
            raise ValueError(f"Invalid kind: {kind}")
        rec = table.get(name)
        return Path(rec.spec_path) if rec and rec.spec_path else None

    # ---- Manifest persistence ----

    def _all_records(self) -> List[SkillRecord]:
        return list(self._skills.values()) + list(self._tools.values()) + list(self._workflows.values())

    def _load_manifest(self) -> None:
        if not self.manifest_path or not self.manifest_path.exists():
            return
        try:
            data = json.loads(self.manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for raw in data.get("records", []):
            try:
                rec = SkillRecord(**raw)
            except (ValueError, TypeError):
                continue
            table = {"skill": self._skills, "tool": self._tools, "workflow": self._workflows}.get(rec.kind)
            if table is not None:
                table[rec.name] = rec

    def _save_manifest(self) -> None:
        if not self.manifest_path:
            return
        payload = {"records": [vars(r) for r in self._all_records()]}
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass
