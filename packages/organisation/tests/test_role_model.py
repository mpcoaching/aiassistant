"""
Tests for organisation package init and imports.
"""

from __future__ import annotations

from role import Agent, Role, RoleStatus


def test_role_creation() -> None:
    role = Role(
        id="role-1",
        name="CEO",
        description="Chief Executive Officer",
        responsibilities=["Set strategy", "Allocate work"],
        authority_ids=["auth-1"],
    )
    assert role.id == "role-1"
    assert role.name == "CEO"
    assert role.status == RoleStatus.ACTIVE


def test_agent_marker() -> None:
    agent = Agent(id="agent-1", name="Bot", marker="ai")
    assert agent.marker.value == "ai"


def test_no_capability_imports() -> None:
    """Organisation domain must not import capability_registry or concepts."""
    import ast
    import os

    source_dir = os.path.join(os.path.dirname(__file__), "..", "src")
    source_dir = os.path.normpath(source_dir)
    for filename in os.listdir(source_dir):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(source_dir, filename)
        with open(path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and (
                "capability_registry" in node.module
                or "capabilities" in node.module
                or "concepts" in node.module
            ):
                raise AssertionError(
                    f"Organisation domain must not import {node.module}"
                )
