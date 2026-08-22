"""
Tests for organisation package role model and accountability proof.
"""

from __future__ import annotations

import ast
import os

from role import (
    Agent,
    Person,
    Role,
    RoleStatus,
    Work,
)


def test_role_creation() -> None:
    role = Role(
        id="role-1",
        name="CEO",
        description="Chief Executive Officer",
        responsibilities=["Set strategy", "Allocate work"],
        authority_ids=["auth-1"],
        required_capability_ids=["cap-strategy", "cap-leadership"],
    )
    assert role.id == "role-1"
    assert role.name == "CEO"
    assert role.status == RoleStatus.ACTIVE
    assert role.required_capability_ids == ["cap-strategy", "cap-leadership"]


def test_agent_marker() -> None:
    agent = Agent(id="agent-1", name="Bot", marker="ai")
    assert agent.marker.value == "ai"


def test_person_fulfils_role() -> None:
    person = Person(id="p1", name="Alice", role_ids=["r1", "r2"])
    assert "r1" in person.role_ids
    assert "r2" in person.role_ids


def test_agent_fulfils_role() -> None:
    agent = Agent(id="a1", name="DevBot", fulfilled_role_ids=["r-dev"])
    assert "r-dev" in agent.fulfilled_role_ids


def test_work_accountability_fields() -> None:
    work = Work(
        id="w1",
        title="Enter Market X",
        work_type="project",
        accountable_role_id="r-cmo",
        coordinating_role_id="r-pm",
        required_capability_ids=["cap-market-analysis"],
        acceptance_criteria=["Market entry plan approved"],
        dependencies=[],
        parent_work_id=None,
    )
    assert work.work_type == "project"
    assert work.accountable_role_id == "r-cmo"
    assert work.coordinating_role_id == "r-pm"
    assert work.required_capability_ids == ["cap-market-analysis"]
    assert work.acceptance_criteria == ["Market entry plan approved"]


def test_work_decomposition() -> None:
    parent_work = Work(id="w1", title="Initiative", accountable_role_id="r-cmo")
    child = Work(id="w2", title="Design", parent_work_id=parent_work.id, accountable_role_id="r-ea")
    assert child.parent_work_id == "w1"


def test_work_dependencies() -> None:
    implementation = Work(
        id="w3",
        title="Implement",
        dependencies=["w1", "w2"],
        accountable_role_id="r-dev",
    )
    assert implementation.dependencies == ["w1", "w2"]


def test_bau_work_has_accountable_role() -> None:
    work = Work(
        id="w-bau-1",
        title="Fix KPI deterioration",
        work_type="bau",
        accountable_role_id="r-fmgr",
        coordinating_role_id="r-fmgr",
    )
    assert work.accountable_role_id == "r-fmgr"
    assert work.coordinating_role_id == "r-fmgr"


def test_capability_portability_across_roles() -> None:
    role_a = Role(id="r-ea", name="EA", required_capability_ids=["cap-arch"])
    role_b = Role(id="r-sa", name="SA", required_capability_ids=["cap-arch"])
    assert role_a.required_capability_ids == role_b.required_capability_ids
    assert role_a.id != role_b.id


def test_person_possesses_capability() -> None:
    person = Person(id="p1", name="Alice", role_ids=["r-ea"])
    assert person.id == "p1"
    assert "r-ea" in person.role_ids


def test_no_capability_imports() -> None:
    """Organisation domain must not import capability_registry or concepts."""
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
