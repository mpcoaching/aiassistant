"""
People/Capability plane — domain models and interfaces (Increment 14).

Exports:
- Person, Agent — workforce records
- Capability — reusable ability definition
- CapabilityAssignment, CapabilityProficiency — possession records
- CapabilityRepository, CapabilityQuery — persistence and query interfaces
- ExecutionAuthorisationPort — Operations authorisation query
"""

from person import Person, PersonStatus
from agent import Agent, AgentMarker, AgentStatus
from capability import (
    Capability,
    CapabilityKind,
    CapabilityStatus,
    CapabilityInterface,
    Parameter,
)
from capability_assignment import CapabilityAssignment, AssignmentType, AssignmentStatus
from capability_proficiency import CapabilityProficiency, ProficiencyLevel
from capability_repository import CapabilityRepository, CapabilityQuery
from execution_authorisation import ExecutionAuthorisationPort, AuthorisationResult

__all__ = [
    "Person",
    "PersonStatus",
    "Agent",
    "AgentMarker",
    "AgentStatus",
    "Capability",
    "CapabilityKind",
    "CapabilityStatus",
    "CapabilityInterface",
    "Parameter",
    "CapabilityAssignment",
    "AssignmentType",
    "AssignmentStatus",
    "CapabilityProficiency",
    "ProficiencyLevel",
    "CapabilityRepository",
    "CapabilityQuery",
    "ExecutionAuthorisationPort",
    "AuthorisationResult",
]
