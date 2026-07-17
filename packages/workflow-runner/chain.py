"""
Workflow Chain Detector — discovers and traverses workflow chains.

A "chain" is a workflow whose steps are other workflows (type: workflow).
This module scans the workflows directory, builds a dependency graph,
and can find the downstream chain from any workflow to the end of its
containing chain(s).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loader import load_workflow, WorkflowLoadError
from models import WorkflowDefinition


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / ".git").exists() or (parent / ".kilo").exists():
            return parent
    return start


class ChainDetectionError(Exception):
    """Raised when chain detection fails."""
    pass


def _scan_workflow_files(search_paths: Optional[List[Path]] = None) -> List[Path]:
    """Find all workflow YAML files in the given directories."""
    if search_paths is None:
        _repo_root = _find_repo_root(Path(__file__).resolve().parent)
        search_paths = [
            _repo_root / "agentic" / "docs" / "workflows",
            _repo_root / "agentic" / "workflows",
        ]

    files: List[Path] = []
    for base in search_paths:
        if not base.exists():
            continue
        for pattern in ("*.yaml", "*.yml"):
            files.extend(base.glob(pattern))
    return sorted(files)


def build_workflow_graph(
    search_paths: Optional[List[Path]] = None,
) -> Dict[str, WorkflowDefinition]:
    """
    Load all workflows and return a map of workflow name -> WorkflowDefinition.

    Args:
        search_paths: Directories to search for workflow files.

    Returns:
        Dictionary mapping workflow names to their definitions.
    """
    graph: Dict[str, WorkflowDefinition] = {}
    for path in _scan_workflow_files(search_paths):
        try:
            wf = load_workflow(path)
            graph[wf.name] = wf
        except WorkflowLoadError:
            continue
    return graph


def build_dependency_graph(
    search_paths: Optional[List[Path]] = None,
) -> Dict[str, List[str]]:
    """
    Build a dependency graph: workflow name -> list of sub-workflow names it references.

    Args:
        search_paths: Directories to search for workflow files.

    Returns:
        Dictionary mapping workflow names to lists of sub-workflow names.
    """
    graph = build_workflow_graph(search_paths)
    deps: Dict[str, List[str]] = {}

    for name, wf in graph.items():
        sub_workflows = [
            step.uses for step in wf.steps if step.type.value == "workflow"
        ]
        deps[name] = sub_workflows

    return deps


def find_downstream_chain(
    workflow_name: str,
    search_paths: Optional[List[Path]] = None,
) -> List[str]:
    """
    Find the downstream chain starting from a given workflow.

    Returns the suffix of the chain root's ordered step list starting from
    ``workflow_name``.  If ``workflow_name`` is not part of any chain,
    returns ``[workflow_name]``.
    """
    if search_paths is None:
        _repo_root = _find_repo_root(Path(__file__).resolve().parent)
        search_paths = [_repo_root / "agentic" / "docs" / "workflows"]

    deps = build_dependency_graph(search_paths)

    reverse: Dict[str, List[str]] = {}
    for parent, children in deps.items():
        for child in children:
            reverse.setdefault(child, []).append(parent)

    if workflow_name not in reverse or not reverse[workflow_name]:
        return [workflow_name]

    chain_roots = [
        name for name, children in deps.items()
        if children and (name not in reverse or not reverse.get(name))
    ]

    longest_chain: List[str] = [workflow_name]
    for root in chain_roots:
        if workflow_name in deps[root]:
            idx = deps[root].index(workflow_name)
            tail = list(deps[root][idx:])
            if len(tail) > len(longest_chain):
                longest_chain = tail

    return longest_chain


def is_chain_workflow(
    workflow_name: str,
    search_paths: Optional[List[Path]] = None,
) -> bool:
    """
    Check if a workflow is part of a chain (i.e., referenced by another workflow).

    Args:
        workflow_name: Name of the workflow to check.
        search_paths: Directories to search for workflow files.

    Returns:
        True if the workflow is referenced by at least one other workflow.
    """
    if search_paths is None:
        _repo_root = _find_repo_root(Path(__file__).resolve().parent)
        search_paths = [_repo_root / "agentic" / "docs" / "workflows"]

    deps = build_dependency_graph(search_paths)
    for parent, children in deps.items():
        if workflow_name in children:
            return True
    return False
