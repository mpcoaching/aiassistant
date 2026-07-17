"""
Intent intake + Recognition (Phase 2, contract C3).

An Intent is origin-agnostic (user request / scheduled job / bus event / alert).
``recognise`` classifies it into a ProblemFrame (resolved ContextRecord). The
v1 implementation uses rule-based classification on keywords; later versions
replace this with an embedding + learned selector without changing the interface.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field

from enterprise_context import (
    ActivityPurpose,
    ContextRecord,
    DecisionContext,
    EnvironmentContext,
    InformationContext,
    ProblemContext,
)


class IntentOrigin(str, Enum):
    USER_REQUEST = "user_request"
    SCHEDULED_JOB = "scheduled_job"
    BUS_EVENT = "bus_event"
    ALERT = "alert"


class Intent(BaseModel):
    id: str
    origin: IntentOrigin
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    declared_context: Optional[dict] = None
    raw: dict = Field(default_factory=dict)


class RecognitionLevel(str, Enum):
    DIRECT_REUSE = "direct_reuse"
    ADAPTATION = "adaptation"
    SYNTHESIS = "synthesis"


class ProblemFrame(BaseModel):
    context: ContextRecord
    confidence: float = 1.0
    recognition_level: RecognitionLevel = RecognitionLevel.DIRECT_REUSE


# ---- v1 keyword-based recogniser (C3 seed) ---------------------------------

_RECOGNITION_RULES = [
    (r"\b(incident|outage|5xx|down|broken|error|spike)\b", ProblemContext.INCIDENT, ActivityPurpose.INVESTIGATE, 0.8),
    (r"\b(restore|fix|resolve|patch)\b", ProblemContext.INCIDENT, ActivityPurpose.EXECUTE, 0.9),
    (r"\b(design|architecture|adr|proposal)\b", ProblemContext.DESIGN, ActivityPurpose.DECIDE, 0.85),
    (r"\b(decision|choose|select|approve)\b", ProblemContext.DECISION, ActivityPurpose.DECIDE, 0.8),
    (r"\b(compliance|audit|verify|checklist)\b", ProblemContext.COMPLIANCE, ActivityPurpose.VALIDATE, 0.85),
    (r"\b(learn|reflect|retro|improve)\b", ProblemContext.LEARNING, ActivityPurpose.OPTIMISE, 0.7),
    (r"\b(explore|brainstorm|ideate|novel)\b", ProblemContext.INNOVATION, ActivityPurpose.EXPLORE, 0.7),
    (r"\b(report|routine|daily|standard)\b", ProblemContext.ROUTINE_OPERATION, ActivityPurpose.EXECUTE, 0.9),
]

_FALLBACK = (ProblemContext.UNKNOWN, ActivityPurpose.INVESTIGATE, 0.3)


def recognise(intent: Intent) -> ProblemFrame:
    text = _extract_text(intent)
    for pattern, problem, activity, confidence in _RECOGNITION_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            level = RecognitionLevel.DIRECT_REUSE if confidence >= 0.8 else RecognitionLevel.ADAPTATION
            return ProblemFrame(
                context=ContextRecord(
                    problem_context=problem,
                    activity_purpose=activity,
                    environment_context=EnvironmentContext.AI_ASSISTED,
                    information_context=InformationContext.INTERNAL_ONLY,
                    decision_context=DecisionContext(),
                ),
                confidence=confidence,
                recognition_level=level,
            )
    problem, activity, confidence = _FALLBACK
    return ProblemFrame(
        context=ContextRecord(
            problem_context=problem,
            activity_purpose=activity,
            environment_context=EnvironmentContext.AI_ASSISTED,
            information_context=InformationContext.ENTERPRISE_KNOWLEDGE,
            decision_context=DecisionContext(),
        ),
        confidence=confidence,
        recognition_level=RecognitionLevel.SYNTHESIS,
    )


def _extract_text(intent: Intent) -> str:
    raw_type = intent.raw.get("type", "")
    if raw_type == "natural_language":
        return intent.raw.get("text", "")
    if raw_type == "structured":
        return " ".join(str(v) for v in intent.raw.get("structured", {}).values())
    if raw_type == "event_ref":
        return intent.raw.get("event_id", "")
    return intent.id
