"""
Tests for the Actor-Organisation boundary (Increment 24X).

Proves that:
- Actor is a people_capability concept, not an organisation concept
- Organisation references actors by ID only
- The architectural boundary is preserved
"""

from __future__ import annotations

import ast
import os

from actor import ActorType
from agent import Agent, AgentMarker

from role import Assignment, Role, Work


def test_organisation_does_not_define_actor_model() -> None:
    """The Actor model lives in people_capability, not in organisation."""
    source_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "people_capability", "src"
    )
    source_dir = os.path.normpath(source_dir)
    assert os.path.isdir(source_dir), "people_capability src directory must exist"
    assert os.path.exists(os.path.join(source_dir, "actor.py")), "actor.py must exist in people_capability"

    org_source_dir = os.path.join(
        os.path.dirname(__file__), "..", "src"
    )
    org_source_dir = os.path.normpath(org_source_dir)
    for filename in os.listdir(org_source_dir):
        if not filename.endswith(".py"):
            continue
        if filename == "__init__.py":
            continue
        path = os.path.join(org_source_dir, filename)
        with open(path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Actor":
                raise AssertionError(
                    "Actor model must not be redefined in organisation; "
                    "it belongs to people_capability"
                )


def test_organisation_can_import_actor_from_people_capability() -> None:
    """Organisation boundary can reference Actor by importing from people_capability."""
    from actor import Actor  # noqa: F401
    assert ActorType.AGENT.value == "agent"
    assert ActorType.PERSON.value == "person"


def test_assignment_assignee_type_matches_actor_type() -> None:
    """Organisation Assignment.assignee_type is compatible with ActorType values."""
    assignment = Assignment(
        id="a1",
        work_id="w1",
        assignee_type=ActorType.AGENT.value,
        assignee_id="assistant",
    )
    assert assignment.assignee_type == "agent"
    assert assignment.assignee_type in (ActorType.AGENT.value, ActorType.PERSON.value, "role")


def test_agent_from_people_capability_is_usable_in_organisation() -> None:
    """The Agent from people_capability can be used with OCP.assign_work."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r-assistant", name="Assistant")
    plane.register_role(role)

    agent = Agent(id="assistant", name="Assistant", marker=AgentMarker.AI)
    work = Work(id="w-a1", title="Task", accountable_role_id="r-assistant")
    assignment = plane.assign_work(work, agent)

    assert assignment.assignee_type == "agent"
    assert assignment.assignee_id == "assistant"
    assert work.assignee_agent_id == "assistant"
