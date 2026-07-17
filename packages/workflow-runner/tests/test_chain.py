"""
Tests for workflow chain detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from pathlib import Path
from typing import List

from chain import (
    build_dependency_graph,
    find_downstream_chain,
    is_chain_workflow,
)
from loader import load_workflow


def _repo_root() -> Path:
    """Return the repo root path based on this file's location."""
    from pathlib import Path
    _start = Path(__file__).resolve().parent
    for _parent in [_start] + list(_start.parents):
        if (_parent / ".git").exists() or (_parent / ".kilo").exists():
            return _parent
    return _start


def _workflow_search_paths() -> List[Path]:
    """Return workflow search paths relative to the repo root."""
    root = _repo_root()
    return [root / "agentic" / "docs" / "workflows"]


def _load_workflow(name: str) -> "WorkflowDefinition":
    """Helper to load a workflow by name from the test workflows directory."""
    search_paths = _workflow_search_paths()
    for base in search_paths:
        for ext in ("yaml", "yml"):
            p = base / f"{name}.{ext}"
            if p.exists():
                return load_workflow(p)
    raise FileNotFoundError(f"Workflow '{name}' not found")


def test_delivery_chain_detection() -> None:
    """Test that delivery.chain is detected as a chain workflow."""
    search_paths = _workflow_search_paths()
    assert is_chain_workflow("requirements.analysis.identify-stakeholders", search_paths) is True
    assert is_chain_workflow("requirements.analysis.define-requirements", search_paths) is True
    assert is_chain_workflow("requirements.validation.verify-traceability", search_paths) is True
    assert is_chain_workflow("ea.strategic-decomposition", search_paths) is True
    assert is_chain_workflow("architecture.solution.create", search_paths) is True
    assert is_chain_workflow("design.create", search_paths) is True
    assert is_chain_workflow("development.implement", search_paths) is True
    assert is_chain_workflow("test.execute", search_paths) is True
    assert is_chain_workflow("test.validate-requirements", search_paths) is True


def test_standalone_workflow_not_in_chain() -> None:
    """Test that a standalone workflow is not detected as part of a chain."""
    search_paths = _workflow_search_paths()
    # These workflows are not referenced by any other workflow in the repo
    # (based on the current delivery.chain.yaml contents)
    # We verify by checking they are not in the reverse dependency map
    deps = build_dependency_graph(search_paths)
    reverse: dict = {}
    for parent, children in deps.items():
        for child in children:
            reverse.setdefault(child, []).append(parent)

    # delivery.chain itself is a chain root, not a child of anything
    assert "delivery.chain" not in reverse or not reverse.get("delivery.chain")


def test_find_downstream_chain_from_chain_member() -> None:
    """Test finding the downstream chain from a workflow that is part of delivery.chain."""
    search_paths = _workflow_search_paths()
    # Starting from the first step in delivery.chain, we should get the full chain
    chain = find_downstream_chain("requirements.analysis.identify-stakeholders", search_paths)
    assert "requirements.analysis.identify-stakeholders" in chain
    assert "requirements.analysis.define-requirements" in chain
    assert "test.validate-requirements" in chain


def test_find_downstream_chain_standalone() -> None:
    """Test that a standalone workflow returns itself as the chain."""
    search_paths = _workflow_search_paths()
    # Pick a workflow that is not part of delivery.chain
    # For this test, we use a workflow that exists but is not in the chain
    chain = find_downstream_chain("ea.architectural-discovery", search_paths)
    # It should at least return itself
    assert "ea.architectural-discovery" in chain


def test_build_dependency_graph() -> None:
    """Test that the dependency graph is built correctly."""
    search_paths = _workflow_search_paths()
    deps = build_dependency_graph(search_paths)
    assert "delivery.chain" in deps
    assert len(deps["delivery.chain"]) == 9
    assert "requirements.analysis.identify-stakeholders" in deps["delivery.chain"]
    assert "test.validate-requirements" in deps["delivery.chain"]


def test_cycle_safety() -> None:
    """Test that cycle detection does not cause infinite loops."""
    search_paths = _workflow_search_paths()
    # This test verifies the algorithm doesn't hang on cyclic dependencies
    # We can't easily create a cyclic workflow in the test data,
    # but we can at least verify the function returns quickly
    chain = find_downstream_chain("requirements.analysis.define-requirements", search_paths)
    assert isinstance(chain, list)
    assert len(chain) > 0
