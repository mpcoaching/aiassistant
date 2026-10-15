"""
Session model + creation (Phase 3, contract C10 / SESSION-MODEL.md).

A Session is a bounded execution of a pattern pipeline. In implementation terms,
a Session *is* a workflow instance (WorkflowState). ``create_session_from_decision``
turns a StrategyDecision into a runnable Session.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from assistant import StrategyDecision
from pydantic import BaseModel, Field


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
    role_override: str | None = None
    participants: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    enabled_pathways: list[str] = Field(default_factory=list)
    disabled_pathways: list[str] = Field(default_factory=list)
    status: str = "pending"


class Session(BaseModel):
    id: str
    intent_id: str
    strategy: str
    pipeline: list[PatternStep] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    workflow_id: str | None = None


def create_session_from_decision(decision: StrategyDecision, context: dict | None = None) -> Session:
    pipeline = [PatternStep(pattern_id=pid) for pid in decision.pattern_pipeline]
    session = Session(
        id=f"ses-{decision.intent_id}",
        intent_id=decision.intent_id,
        strategy=decision.chosen_strategy.value,
        pipeline=pipeline,
        context=context or {},
    )
    return session
