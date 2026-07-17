"""
Enterprise Context model (Phase 2, contract C3 / anchor §5).

Re-exports the typed ContextRecord plus the five orthogonal context enums
from the anchor doc. No framework concepts leak here (Principle 10).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProblemContext(str, Enum):
    ROUTINE_OPERATION = "routine_operation"
    INCIDENT = "incident"
    INNOVATION = "innovation"
    INVESTIGATION = "investigation"
    DESIGN = "design"
    DECISION = "decision"
    OPTIMISATION = "optimisation"
    COMPLIANCE = "compliance"
    LEARNING = "learning"
    UNKNOWN = "unknown"


class EnvironmentContext(str, Enum):
    HUMANS_ONLY = "humans_only"
    AI_ASSISTED = "ai_assisted"
    API_AUTOMATED = "api_automated"
    WORKFLOW_DRIVEN = "workflow_driven"
    MCP_INTEROP = "mcp_interop"
    MULTI_SYSTEM = "multi_system"


class InformationContext(str, Enum):
    INTERNAL_ONLY = "internal_only"
    CUSTOMER_DATA = "customer_data"
    REGULATED = "regulated"
    HISTORIC_DECISIONS = "historic_decisions"
    ENTERPRISE_KNOWLEDGE = "enterprise_knowledge"
    EXTERNAL_SYSTEMS = "external_systems"


class ActivityPurpose(str, Enum):
    EXPLORE = "explore"
    DECIDE = "decide"
    APPROVE = "approve"
    VALIDATE = "validate"
    REVIEW = "review"
    EXECUTE = "execute"
    LEARN = "learn"
    OPTIMISE = "optimise"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"


class ConfidenceRequired(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXHAUSTIVE = "exhaustive"


class AuthorityModel(str, Enum):
    SINGLE_AUTHORITY = "single_authority"
    CONSENSUS = "consensus"
    DEMOCRATIC = "democratic"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    SEMI_REVERSIBLE = "semi_reversible"
    IRREVERSIBLE = "irreversible"


class CostVsQuality(str, Enum):
    FAST_CHEAP = "fast_cheap"
    BALANCED = "balanced"
    THOROUGH = "thorough"


class DecisionContext(BaseModel):
    confidence_required: ConfidenceRequired = ConfidenceRequired.MEDIUM
    authority_model: AuthorityModel = AuthorityModel.SINGLE_AUTHORITY
    reversibility: Reversibility = Reversibility.REVERSIBLE
    mandatory_policy_checks: List[str] = Field(default_factory=list)
    human_approval_required: bool = False
    timebox_seconds: int = 0
    cost_vs_quality: CostVsQuality = CostVsQuality.BALANCED


class ContextRecord(BaseModel):
    problem_context: ProblemContext = ProblemContext.ROUTINE_OPERATION
    environment_context: EnvironmentContext = EnvironmentContext.AI_ASSISTED
    information_context: InformationContext = InformationContext.INTERNAL_ONLY
    activity_purpose: ActivityPurpose = ActivityPurpose.EXECUTE
    decision_context: DecisionContext = Field(default_factory=DecisionContext)
