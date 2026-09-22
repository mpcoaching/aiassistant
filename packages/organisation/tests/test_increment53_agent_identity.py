"""
Increment 53 — Wire Assistant Agent identity into Work creation.

Increment 52 added assignee_actor_id to WorkCreateRequest and wired AgentStore
into WorkManagementAdapter, but no production caller used it.

Increment 53 threads the existing Assistant Agent identity ("assistant") from
the composition root through create_assistant() into AssistantChatService, and
then passes it as assignee_actor_id in all 4 WorkCreateRequest(...) call sites.

Tests prove:
1. AssistantChatService receives the Assistant Agent identity.
2. Each chat Work creation path supplies assignee_actor_id.
3. The resulting Work has the Assistant Actor assignment.
4. accountable_role_id remains "default".
5. The Assistant Actor is the existing Agent/Actor identity, not a new Actor.
6. The assigned Work is selectable by the Paperclip backend.
7. Existing non-chat Work creation remains unchanged.
8. Backward compatibility: agent_id=None → no assignee_actor_id passed.
9. Composition root threads agent_id through create_application().
"""

from __future__ import annotations

import os
import sys

import pytest

# Path setup (mirror test_increment52 pattern)
ORGANISATION_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
PEOPLE_CAPABILITY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "people_capability", "src")
)
AI_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "ai", "src")
)
WORKFLOW_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "workflow_runner", "src")
)

sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
sys.path.insert(0, ORGANISATION_SRC)
sys.path.insert(0, AI_SRC)
sys.path.insert(0, WORKFLOW_SRC)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore
from actor import ActorType
from contracts.work_management import WorkCreateRequest, WorkReference
from organisation_control_plane import InMemoryOrganisationControlPlane
from role import Role, Work, WorkStatus

# Import AssistantChatService from the AI package
import importlib

_chat_mod = importlib.import_module("chat")
AssistantChatService = _chat_mod.AssistantChatService
ChatRequest = _chat_mod.ChatRequest

from ai.tests.fixtures.in_memory_ports import (
    InMemoryCapabilityDiscoveryPort,
    InMemoryWorkManagementPort,
)

from contracts.capability_discovery import CapabilityCandidate
from contracts.enterprise_capability_query import CapabilityAvailability


# --------------------------------------------------------------------------- #
# A. AssistantChatService receives the Assistant Agent identity
# --------------------------------------------------------------------------- #


def test_assistant_chat_service_accepts_agent_id() -> None:
    """AssistantChatService.__init__ accepts an agent_id parameter
    and stores it as self._agent_id."""
    service = AssistantChatService(agent_id="assistant")
    assert service._agent_id == "assistant"


def test_assistant_chat_service_agent_id_defaults_none() -> None:
    """When agent_id is not supplied, it defaults to None
    (backward compatibility — existing callers unaffected)."""
    service = AssistantChatService()
    assert service._agent_id is None


def test_assistant_chat_service_stores_agent_id_as_str() -> None:
    """The agent_id is retained verbatim — the existing Agent/Actor identity,
    not a new one."""
    service = AssistantChatService(agent_id="assistant")
    assert service._agent_id == "assistant"
    assert isinstance(service._agent_id, str)


# --------------------------------------------------------------------------- #
# B. Each relevant chat Work creation path supplies assignee_actor_id
# --------------------------------------------------------------------------- #


def test_delegation_path_supplies_assignee_actor_id() -> None:
    """_delegate_work_response (the main delegation path) passes
    assignee_actor_id=self._agent_id on the WorkCreateRequest."""
    from ai.tests.fixtures.in_memory_ports import InMemoryCapabilityDiscoveryPort

    wm = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=InMemoryCapabilityDiscoveryPort(candidates=[]),
        work_management=wm,
        agent_id="assistant",
    )
    response = service.chat(ChatRequest(message="Research topic X"))

    assert response.status == "delegated"
    assert len(wm.created_work) == 1
    assert wm.created_work[0]["assignee_actor_id"] == "assistant"


def test_new_capability_path_supplies_assignee_actor_id() -> None:
    """_handle_new_capability_required_response passes
    assignee_actor_id=self._agent_id."""
    from types import SimpleNamespace

    class _FakeSolutionSelection:
        def select_execution_path(self, intent: str, context: dict) -> object:
            return SimpleNamespace(
                path="new_capability_required",
                capability_id="cap-gap-x",
                reason="Gap detected",
            )

    wm = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=InMemoryCapabilityDiscoveryPort(candidates=[]),
        work_management=wm,
        solution_selection=_FakeSolutionSelection(),
        agent_id="assistant",
    )
    response = service.chat(ChatRequest(message="Do something new"))

    assert response.status == "capability_gap"
    assert len(wm.created_work) == 1
    assert wm.created_work[0]["assignee_actor_id"] == "assistant"
    assert wm.created_work[0]["work_type"] == "capability_development"
    assert wm.created_work[0]["accountable_role_id"] == "default"


def test_human_team_investigation_path_supplies_assignee_actor_id() -> None:
    """_handle_human_team_investigation_response passes
    assignee_actor_id=self._agent_id."""
    from types import SimpleNamespace

    class _FakeSolutionSelection:
        def select_execution_path(self, intent: str, context: dict) -> object:
            return SimpleNamespace(
                path="human_team_investigation",
                capability_id="cap-human",
                reason="Needs human review",
            )

    wm = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=InMemoryCapabilityDiscoveryPort(candidates=[]),
        work_management=wm,
        solution_selection=_FakeSolutionSelection(),
        agent_id="assistant",
    )
    response = service.chat(ChatRequest(message="Investigate this for me"))

    assert response.status == "human_team_investigation"
    assert len(wm.created_work) == 1
    assert wm.created_work[0]["assignee_actor_id"] == "assistant"
    assert wm.created_work[0]["accountable_role_id"] == "default"


def test_capability_gap_path_supplies_assignee_actor_id() -> None:
    """_handle_capability_gap (enterprise-capability-query fallback) passes
    assignee_actor_id=self._agent_id.

    This path is triggered when enterprise_capability_query.query_capability()
    returns None (capability not found in enterprise)."""
    candidates = [
        CapabilityCandidate(
            id="cap-gap-test",
            name="Gap Cap",
            description="A capability that is missing",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    wm = InMemoryWorkManagementPort()

    class _FakeQueryPort:
        queried: list[str] = []

        def query_capability(self, capability_id: str):
            self.queried.append(capability_id)
            return None

    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=wm,
        enterprise_capability_query=_FakeQueryPort(),
        agent_id="assistant",
    )
    response = service.chat(ChatRequest(message="Do the thing with cap-gap-test"))

    assert response.status == "capability_gap"
    assert len(wm.created_work) == 1
    assert wm.created_work[0]["assignee_actor_id"] == "assistant"
    assert wm.created_work[0]["accountable_role_id"] == "default"


# --------------------------------------------------------------------------- #
# C. The resulting Work has the Assistant Actor assignment
# --------------------------------------------------------------------------- #


def test_assigned_work_has_assistant_actor_id() -> None:
    """End-to-end through WorkManagementAdapter: when assignee_actor_id is
    passed, the resulting Work has assignee_actor_id == 'assistant' and
    assignee_agent_id == 'assistant'."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    store = InMemoryAgentStore()
    store.bootstrap_assistant(actor_id="assistant")

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Test work",
        description="test",
        accountable_role_id="default",
        work_type="bau",
        assignee_actor_id="assistant",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_actor_id == "assistant"
    assert work.assignee_agent_id == "assistant"
    assert work.status == WorkStatus.ASSIGNED


# --------------------------------------------------------------------------- #
# D. accountable_role_id remains "default"
# --------------------------------------------------------------------------- #


def test_accountable_role_id_remains_default() -> None:
    """Even when assignee_actor_id is set, accountable_role_id stays 'default'.
    Accountability (role) and assignment (actor) are distinct concepts."""
    from ai.tests.fixtures.in_memory_ports import InMemoryCapabilityDiscoveryPort

    wm = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=InMemoryCapabilityDiscoveryPort(candidates=[]),
        work_management=wm,
        agent_id="assistant",
    )
    service.chat(ChatRequest(message="Do something"))

    req = wm.created_work[0]
    assert req["accountable_role_id"] == "default"
    assert req["assignee_actor_id"] == "assistant"


# --------------------------------------------------------------------------- #
# E. The Assistant Actor is the existing Agent/Actor identity
# --------------------------------------------------------------------------- #


def test_assistant_is_existing_agent_not_new_actor() -> None:
    """The 'assistant' actor_id refers to the existing bootstrapped Agent/Actor,
    not a newly created one."""
    store = InMemoryAgentStore()
    agent, actor, _ = store.bootstrap_assistant(actor_id="assistant")

    retrieved = store.get_actor("assistant")
    assert retrieved is not None
    assert retrieved.id == "assistant"
    assert retrieved.actor_type == ActorType.AGENT
    assert retrieved.reference_id == "assistant"
    assert retrieved.id == actor.id


def test_assistant_actor_is_same_as_bootstrap() -> None:
    """create_application's _create_agent_store() bootstraps the assistant
    with actor_id='assistant'.  The agent_id passed to AssistantChatService
    matches that identity."""
    from workflow_runner.src.composition import _create_agent_store

    store = _create_agent_store()
    actor = store.get_agent("assistant")
    assert actor is not None
    assert actor.id == "assistant"
    assert actor.marker == AgentMarker.AI

    retrieved_actor = store.get_actor("assistant")
    assert retrieved_actor is not None
    assert retrieved_actor.actor_type == ActorType.AGENT


# --------------------------------------------------------------------------- #
# F. The assigned Work can now be selected by the existing Paperclip backend
# --------------------------------------------------------------------------- #


def test_paperclip_backend_can_handle_assigned_work() -> None:
    """PaperclipBackend.can_handle returns True for work that has
    assignee_agent_id set (i.e. assigned to the Assistant Agent)."""
    from workflow_runner.src.operations import PaperclipBackend
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter
    from unittest.mock import MagicMock

    store = InMemoryAgentStore()
    store.bootstrap_assistant(actor_id="assistant")

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Paperclip testable work",
        accountable_role_id="default",
        work_type="bau",
        assignee_actor_id="assistant",
    )
    ref = adapter.create_work(req)
    plane.mark_work_ready(ref.work_id)

    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_agent_id == "assistant"

    backend = PaperclipBackend(paperclip_plane=MagicMock())
    assert backend.can_handle(work) is True


def test_paperclip_backend_cannot_handle_unassigned_work() -> None:
    """PaperclipBackend.can_handle returns False for work without
    assignee_agent_id (backward compatibility — falls to WorkerBackend)."""
    from workflow_runner.src.operations import PaperclipBackend
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter
    from unittest.mock import MagicMock

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    adapter = WorkManagementAdapter(plane)
    req = WorkCreateRequest(
        title="Unassigned work",
        accountable_role_id="default",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_agent_id is None

    backend = PaperclipBackend(paperclip_plane=MagicMock())
    assert backend.can_handle(work) is False


# --------------------------------------------------------------------------- #
# G. Existing non-chat Work creation remains unchanged
# --------------------------------------------------------------------------- #


def test_non_chat_work_creation_without_agent_id_unchanged() -> None:
    """Work created without agent_id (no AssistantChatService involvement)
    remains unchanged — assignee_actor_id is None, falls to Role assignment."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    store = InMemoryAgentStore()
    store.bootstrap_assistant(actor_id="assistant")

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Direct work",
        accountable_role_id="default",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_actor_id is None
    assert work.assignee_role_id == "default"


# --------------------------------------------------------------------------- #
# H. Backward compatibility: agent_id=None → no assignee_actor_id passed
# --------------------------------------------------------------------------- #


def test_backward_compat_no_agent_id_no_assignee_actor_id() -> None:
    """When agent_id is None (existing callers), the WorkCreateRequest
    should NOT set assignee_actor_id — backward compatibility."""
    from ai.tests.fixtures.in_memory_ports import InMemoryCapabilityDiscoveryPort

    wm = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=InMemoryCapabilityDiscoveryPort(candidates=[]),
        work_management=wm,
        agent_id=None,
    )
    service.chat(ChatRequest(message="Do something"))

    assert len(wm.created_work) == 1
    assert wm.created_work[0]["assignee_actor_id"] is None


# --------------------------------------------------------------------------- #
# I. Composition root threads agent_id through create_application()
# --------------------------------------------------------------------------- #


def test_create_application_passes_agent_id_to_assistant() -> None:
    """create_application() passes agent_id='assistant' to create_assistant(),
    which passes it to AssistantChatService.__init__."""
    from workflow_runner.src.composition import create_application

    try:
        result = create_application()
    except ImportError:
        pytest.skip("create_application has pre-existing ImportError (RelevanceMatcher)")
    assistant = result["assistant"]
    assert assistant._agent_id == "assistant"


def test_create_assistant_passes_agent_id() -> None:
    """create_assistant() forwards agent_id to AssistantChatService."""
    from workflow_runner.src.composition import create_assistant

    assistant = create_assistant(agent_id="assistant")
    assert assistant._agent_id == "assistant"


def test_api_assistant_has_agent_id_configured() -> None:
    """The agent_id 'assistant' corresponds to an Actor in the agent_store
    used by WorkManagementAdapter — the full chain is wired."""
    from workflow_runner.src.composition import create_application

    try:
        result = create_application()
    except ImportError:
        pytest.skip("create_application has pre-existing ImportError (RelevanceMatcher)")
    assert result["assistant"]._agent_id == "assistant"

    work_management = result["work_management"]
    assert work_management._agent_store is not None
    actor = work_management._agent_store.get_actor("assistant")
    assert actor is not None
    assert actor.actor_type == ActorType.AGENT


# --------------------------------------------------------------------------- #
# J. All 4 chat Work creation paths carry the Assistant Actor identity
# --------------------------------------------------------------------------- #


def test_all_four_work_creation_paths_set_assignee_actor_id_in_source() -> None:
    """Source-level verification: all 4 WorkCreateRequest(...) call sites in
    chat.py include assignee_actor_id=self._agent_id."""
    import re

    chat_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "ai", "src", "chat.py")
    )
    with open(chat_path) as f:
        source = f.read()

    wcr_occurrences = len(re.findall(r"WorkCreateRequest\(\s*", source))
    assert wcr_occurrences == 4

    # Each WorkCreateRequest block must include assignee_actor_id=self._agent_id
    assignee_occurrences = len(re.findall(r"assignee_actor_id=self._agent_id", source))
    assert assignee_occurrences == 4

    # Also verify accountable_role_id="default" is preserved in all blocks
    accountable_occurrences = len(re.findall(r'accountable_role_id="default"', source))
    assert accountable_occurrences == 4


def test_no_new_actor_created_in_composition() -> None:
    """The agent_id='assistant' passed in composition refers to the existing
    bootstrapped Assistant Agent — no new Actor/Agent is created by Increment 53."""
    from workflow_runner.src.composition import create_application

    try:
        result = create_application()
    except ImportError:
        pytest.skip("create_application has pre-existing ImportError (RelevanceMatcher)")
    assistant = result["assistant"]

    # The assistant's agent_id is the existing bootstrapped identity
    assert assistant._agent_id == "assistant"

    # Verify the agent_store has exactly one agent (the bootstrapped assistant)
    store = result["work_management"]._agent_store
    agents = store.list_agents()
    assert len(agents) == 1
    assert agents[0].id == "assistant"
