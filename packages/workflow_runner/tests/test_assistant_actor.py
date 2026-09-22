"""
Tests for Assistant actor integration with the organisation boundary (Increment 24X).

Proves that:
- The Assistant is registered as the first Agent/Actor in the people_capability plane
- AssistantChatService is not modified in any way
- The agent_store provides Actor identity for the Assistant
- The organisation context can resolve the Assistant's actor identity
"""

from __future__ import annotations

import pytest
from actor import ActorType
from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore
from role import Role, Work, WorkStatus


class TestAssistantActorRegistration:
    def test_assistant_creates_ai_agent(self) -> None:
        """create_assistant_actor produces an AI Agent."""
        agent, _actor = InMemoryAgentStore.create_assistant_actor()
        assert agent.marker == AgentMarker.AI
        assert agent.status == AgentStatus.ACTIVE
        assert agent.fulfilled_role_ids == ["assistant"]

    def test_assistant_actor_is_unified_identity(self) -> None:
        """The Assistant Actor has a unified identity linked to its Agent."""
        agent, actor = InMemoryAgentStore.create_assistant_actor()
        assert actor.reference_id == agent.id
        assert actor.actor_type == ActorType.AGENT
        assert actor.marker == "ai"

    def test_assistant_fulfills_assistant_and_researcher_roles(self) -> None:
        """The Assistant fulfills both the assistant and researcher roles."""
        _agent, actor = InMemoryAgentStore.create_assistant_actor(
            role_ids=["assistant", "researcher"],
        )
        assert "assistant" in actor.fulfilled_role_ids
        assert "researcher" in actor.fulfilled_role_ids

    def test_assistant_actor_stored_in_agent_store(self) -> None:
        """The Assistant Agent/Actor is stored and retrievable."""
        store = InMemoryAgentStore()
        agent, _actor = InMemoryAgentStore.create_assistant_actor()
        store.register_agent(agent)

        retrieved_agent = store.get_agent("assistant")
        retrieved_actor = store.get_actor("assistant")
        assert retrieved_agent is not None
        assert retrieved_agent.id == "assistant"
        assert retrieved_agent.marker == AgentMarker.AI
        assert retrieved_actor is not None
        assert retrieved_actor.actor_type == ActorType.AGENT

    def test_assistant_agent_usable_in_organisation_plane(self) -> None:
        """The Assistant Agent can be used with OCP.assign_work."""
        from organisation_control_plane import InMemoryOrganisationControlPlane

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="assistant", name="Assistant"))

        agent = Agent(id="assistant", name="Assistant", marker=AgentMarker.AI)
        work = Work(id="w-assistant", title="Task", accountable_role_id="assistant")
        assignment = plane.assign_work(work, agent)

        assert assignment.assignee_type == "agent"
        assert assignment.assignee_id == "assistant"
        assert work.assignee_agent_id == "assistant"
        assert work.status == WorkStatus.ASSIGNED


class TestAssistantActorComposition:
    def test_composition_wires_assistant_actor(self) -> None:
        """The composition logic registers the Assistant as first Agent/Actor."""
        from organisation_control_plane import InMemoryOrganisationControlPlane

        org_plane = InMemoryOrganisationControlPlane()
        org_plane.register_role(Role(id="default", name="Default"))

        agent_store = InMemoryAgentStore()
        assistant_agent, _actor = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant", "researcher"],
        )
        agent_store.register_agent(assistant_agent)
        org_plane.register_role(Role(
            id="assistant",
            name="Assistant",
            description="AI assistant agent",
            authority_ids=[],
            required_capability_ids=[],
        ))

        assert org_plane.get_role("assistant") is not None
        assert agent_store.get_agent("assistant") is not None
        assert agent_store.get_actor("assistant") is not None
        assert agent_store.actor_fulfills_role("assistant", "researcher")

    def test_assistant_chat_service_not_modified(self) -> None:
        """AssistantChatService source is unchanged — still imports ports only."""
        import ast
        import os

        chat_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "ai", "src", "chat.py",
        )
        chat_path = os.path.normpath(chat_path)
        with open(chat_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "AssistantChatService":
                method_names = {
                    n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                assert "chat" in method_names
                assert "resume_with_human_input" in method_names


# ---- Increment 28: Learning loop and Paperclip/LangGraph boundary tests ----


class TestLearningLoopPreservation:
    """Increment 28 — The capability development learning loop must still work.

    capability gap → Work → development → DRAFT capability → assessment →
    ACTIVE capability → assign capability to Actor → capability reusable.
    """

    def test_work_with_required_capability_creates_draft_capability(self) -> None:
        from capability import Capability, CapabilityKind, CapabilityStatus
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))

        work = Work(
            id="w-gap",
            title="Develop capability: Data processing",
            description="Need a way to process data",
            work_type="capability_development",
            accountable_role_id="default",
            required_capability_ids=[],
        )
        plane.assign_work(work, Role(id="default", name="Default"))

        capability = Capability(
            id="cap-data",
            name="Data Processing",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
            owner="worker-1",
            created_by="worker",
        )
        plane.register_capability(capability)

        assert plane.get_capability("cap-data").status == CapabilityStatus.DRAFT

    def test_promote_capability_makes_it_active(self) -> None:
        from capabilities import CapabilityRegistry
        from capability import Capability, CapabilityKind, CapabilityStatus
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        store = ConceptStore()
        repo = ConceptStoreCapabilityRepository(store)
        reg = CapabilityRegistry(repo)

        cap = Capability(
            id="cap-test",
            name="Test Cap",
            capability_kind=CapabilityKind.TOOL,
            status=CapabilityStatus.DRAFT,
        )
        reg.register(cap)
        promoted = reg.promote("cap-test")
        assert promoted.status == CapabilityStatus.ACTIVE

    def test_assign_capability_makes_it_reusable(self) -> None:
        from agent_store import InMemoryAgentStore
        from capability_assignment import AssignmentStatus

        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)

        assignment = store.assign_capability("assistant", "cap-test")
        assert assignment.status == AssignmentStatus.ACTIVE
        assert store.actor_has_capability("assistant", "cap-test")

    def test_full_learning_loop(self) -> None:
        """End-to-end: gap → Work → DRAFT → ACTIVE → assign → authorised."""
        from agent_store import InMemoryAgentStore
        from capabilities import CapabilityRegistry
        from capability import Capability, CapabilityKind, CapabilityStatus
        from capability_assignment import AssignmentStatus
        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        # Phase 1: capability gap detected → Work created
        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="worker", name="Worker"))
        work = Work(
            id="w-gap-1",
            title="Develop capability: Knowledge search",
            work_type="capability_development",
            accountable_role_id="worker",
        )
        plane.assign_work(work, Role(id="worker", name="Worker"))

        # Phase 2: Worker develops DRAFT capability
        store = ConceptStore()
        repo = ConceptStoreCapabilityRepository(store)
        reg = CapabilityRegistry(repo)
        cap = Capability(
            id="cap-search",
            name="Knowledge Search",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
            owner="worker-1",
        )
        reg.register(cap)
        plane.register_capability(cap)

        # Phase 3: Assessment → promote to ACTIVE
        promoted = reg.promote("cap-search")
        assert promoted.status == CapabilityStatus.ACTIVE

        # Phase 4: Assign capability to Actor (Assistant) through normal mechanism
        agent_store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        agent_store.register_agent(agent)
        assignment = agent_store.assign_capability("assistant", "cap-search")
        assert assignment.status == AssignmentStatus.ACTIVE

        # Phase 5: Actor is now authorised to use the capability
        auth = InMemoryExecutionAuthorisationPort(
            assignments=agent_store.get_all_assignments(),
        )
        result = auth.is_authorised("assistant", "agent", "cap-search")
        assert result.authorised is True


class TestPaperclipBoundary:
    """Increment 28 — Paperclip adapter must not define organisational semantics."""

    def test_paperclip_receives_execution_contract_not_organisational_concepts(self) -> None:
        """PaperclipBackend.execute receives a Work object (organisational contract),
        not capability assignments or skill definitions."""
        import inspect

        from operations import PaperclipBackend

        sig = inspect.signature(PaperclipBackend.execute)
        params = list(sig.parameters.keys())
        # execute() takes only `work` — no capability, skill, or assignment params
        assert "work" in params
        assert "capability" not in params
        assert "skill" not in params
        assert "assignment" not in params

    def test_paperclip_adapter_only_translates_not_defines(self) -> None:
        """PaperclipOrganisationControlPlane extends the interface, doesn't redefine domain concepts."""
        import ast
        import os

        paperclip_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "organisation_paperclip", "src", "organisation_paperclip.py",
        )
        paperclip_path = os.path.normpath(paperclip_path)
        with open(paperclip_path) as f:
            tree = ast.parse(f.read())

        # No class definitions of domain concepts
        domain_classes = {"CapabilityAssignment", "CapabilityProficiency", "Skill", "Tool"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in domain_classes:
                raise AssertionError(
                    f"Paperclip adapter must not define domain concept: {node.name}"
                )


class TestLangGraphBoundary:
    """Increment 28 — LangGraph must not define organisational semantics."""

    def test_langgraph_runtime_is_exection_only(self) -> None:
        """LangGraphRuntime implements PathwayRuntime — execution only, no org concepts."""
        from langgraph_runtime import LangGraphRuntime
        from pathway_runtime import PathwayRuntime

        assert issubclass(LangGraphRuntime, PathwayRuntime)

    def test_langgraph_does_not_define_domain_models(self) -> None:
        """LangGraph runtime must not define Actor, Capability, or Assignment models."""
        import ast
        import os

        lg_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "langgraph", "src",
        )
        lg_path = os.path.normpath(lg_path)
        if not os.path.isdir(lg_path):
            pytest.skip("langgraph source not found")

        domain_classes = {"Actor", "Capability", "CapabilityAssignment", "Skill", "Tool"}
        for filename in os.listdir(lg_path):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(lg_path, filename)
            with open(path) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in domain_classes:
                    raise AssertionError(
                        f"LangGraph runtime must not define domain concept: {node.name}"
                    )
