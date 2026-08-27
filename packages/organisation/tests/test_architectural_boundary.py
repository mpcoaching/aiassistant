"""
Architectural boundary tests for Increment 21Z.

These tests verify that the organisational boundary is correctly maintained
and that operational backend details do not leak into higher layers.
"""

from __future__ import annotations

import ast
import os

import pytest


def test_api_does_not_import_paperclip() -> None:
    """The API transport layer must not import Paperclip modules."""
    api_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "workflow_runner", "api.py"
    )
    api_path = os.path.normpath(api_path)
    with open(api_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "organisation_paperclip" not in node.module, (
                "API layer must not import organisation_paperclip"
            )
            assert "paperclip" not in node.module, (
                "API layer must not import paperclip modules"
            )


def test_assistant_does_not_import_operational_backends() -> None:
    """The Assistant must not import operational backend implementations."""
    chat_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "ai", "src", "chat.py"
    )
    chat_path = os.path.normpath(chat_path)
    with open(chat_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "organisation_paperclip" not in node.module, (
                "Assistant must not import organisation_paperclip"
            )
            assert "paperclip" not in node.module, (
                "Assistant must not import paperclip modules"
            )


def test_organisation_control_plane_has_no_execution_methods() -> None:
    """OrganisationControlPlane must not expose operational execution methods."""
    source_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "organisation_control_plane.py"
    )
    source_path = os.path.normpath(source_path)
    with open(source_path) as f:
        tree = ast.parse(f.read())
    execution_methods = {
        "trigger_execution",
        "wait_for_execution",
        "get_heartbeat_run",
        "get_heartbeat_runs_for_issue",
        "create_company",
        "create_agent",
        "execute_work",
        "run_agent",
        "invoke_tool",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "OrganisationControlPlane":
            method_names = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            leaked = execution_methods & method_names
            assert not leaked, (
                f"OrganisationControlPlane must not expose execution methods: {leaked}"
            )


def test_composition_boundary_exists() -> None:
    """Organisation composition must be the single point of backend selection."""
    from organisation.src.composition import create_organisation_control_plane
    from organisation_control_plane import OrganisationControlPlane

    plane = create_organisation_control_plane()
    assert isinstance(plane, OrganisationControlPlane)
