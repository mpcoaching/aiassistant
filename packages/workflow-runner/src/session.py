"""
Session model + creation (Phase 3, contract C10 / SESSION-MODEL.md).

A Session is a bounded execution of a pattern pipeline. In implementation terms,
a Session *is* a workflow instance (WorkflowState). ``create_session_from_decision``
turns a StrategyDecision into a runnable Session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from assistant import StrategyDecision
from db import create_workflow_state


class SessionStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    ESCALATED = "escalated"


class PatternStep(BaseModel):
    pattern_id: str
    role_override: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    enabled_pathways: List[str] = Field(default_factory=list)
    disabled_pathways: List[str] = Field(default_factory=list)
    status: str = "pending"


class Session(BaseModel):
    id: str
    intent_id: str
    strategy: str
    pipeline: List[PatternStep] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    workflow_id: Optional[str] = None


def create_session_from_decision(decision: StrategyDecision, context: Optional[dict] = None) -> Session:
    pipeline = [PatternStep(pattern_id=pid) for pid in decision.pattern_pipeline]
    session = Session(
        id=f"ses-{decision.intent_id}",
        intent_id=decision.intent_id,
        strategy=decision.chosen_strategy.value,
        pipeline=pipeline,
        context=context or {},
    )
    return session
