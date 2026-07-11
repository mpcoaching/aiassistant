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


class ChainDetectionError(Exception):
    """Raised when chain detection fails."""
    pass


def _scan_workflow_files(search_paths: Optional[List[Path]] = None) -> List[Path]:
    """Find all workflow YAML files in the given directories."""
    if search_paths is None:
        # Resolve relative to the repo root (five levels up from this file)
        _repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
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

    Starting from `workflow_name`, follow the dependency graph forward
    through any workflow that references it, then continue following
    that workflow's sub-workflows, until no further continuation exists.

    If multiple chains contain the workflow, returns the longest path
    to the end. Cycles are detected and broken safely.

    Args:
        workflow_name: Name of the workflow to start from.
        search_paths: Directories to search for workflow files.

    Returns:
        Ordered list of workflow names from the starting workflow to the
        end of its containing chain. Returns [workflow_name] if it is not
        part of any chain.
    """
    if search_paths is None:
        _repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        search_paths = [_repo_root / "agentic" / "docs" / "workflows"]

    deps = build_dependency_graph(search_paths)

    # Find all workflows that reference workflow_name (reverse deps)
    reverse: Dict[str, List[str]] = {}
    for parent, children in deps.items():
        for child in children:
            reverse.setdefault(child, []).append(parent)

    # If nothing references this workflow, it's a standalone workflow
    if workflow_name not in reverse or not reverse[workflow_name]:
        return [workflow_name]

    # Find all chains that contain this workflow
    # A chain is a path from some root workflow to a leaf workflow
    # where each step is a workflow reference

    def find_chain_roots(name: str, visited: Set[str]) -> List[str]:
        """Find all root workflows that eventually lead to `name`."""
        roots: List[str] = []
        for parent in reverse.get(name, []):
            if parent in visited:
                continue  # cycle guard
            visited.add(parent)
            # Check if parent is itself referenced by another workflow
            parents_parents = reverse.get(parent, [])
            if not parents_parents:
                roots.append(parent)
            else:
                roots.extend(find_chain_roots(parent, visited))
        return roots

    chain_roots = find_chain_roots(workflow_name, set())

    # For each chain root, trace forward to the end
    def trace_forward(start: str, visited: Set[str]) -> List[str]:
        """Trace a chain from start to the end."""
        chain = [start]
        current = start
        while current in deps and deps[current]:
            next_workflows = [w for w in deps[current] if w not in visited]
            if not next_workflows:
                break
            visited.add(current)
            # Follow the first valid next workflow
            current = next_workflows[0]
            chain.append(current)
        return chain

    # Find the longest chain that includes workflow_name
    longest_chain: List[str] = [workflow_name]
    for root in chain_roots:
        chain = trace_forward(root, set())
        if workflow_name in chain:
            idx = chain.index(workflow_name)
            tail = chain[idx:]
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
        _repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        search_paths = [_repo_root / "agentic" / "docs" / "workflows"]

    deps = build_dependency_graph(search_paths)
    for parent, children in deps.items():
        if workflow_name in children:
            return True
    return False
