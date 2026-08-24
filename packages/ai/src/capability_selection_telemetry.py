"""
Increment 21K — Capability selection telemetry.

Records observational events for capability matching and selection
without changing production behaviour or introducing new infrastructure.

This module is strictly measurement-only. It does not modify matching,
decision policy, execution, or response behaviour.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("ai.capability_selection_telemetry")


@dataclass
class CapabilitySelectionEvent:
    """Observational record of a capability matching/selection event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_text: str = ""
    session_id: str | None = None
    candidate_ids: list[str] = field(default_factory=list)
    candidate_scores: list[float] = field(default_factory=list)
    top_score: float = 0.0
    score_gap: float = 0.0
    candidate_count: int = 0
    interaction_type: str = "select"
    user_action: str | None = None
    selected_capability_id: str | None = None


class CapabilitySelectionTelemetry:
    """Thread-safe in-memory store for capability selection events.

    This is measurement instrumentation only. Events are recorded but
    do not affect matching, decision policy, or execution behaviour.
    """

    def __init__(self) -> None:
        self._events: list[CapabilitySelectionEvent] = []
        self._lock = threading.Lock()

    def record_match_event(
        self,
        request_text: str,
        session_id: str | None,
        candidates: list[Any],
        interaction_type: str,
    ) -> CapabilitySelectionEvent:
        """Record a capability match event at the point candidates are presented."""
        candidate_ids = [c.id for c in candidates]
        candidate_scores = [c.confidence for c in candidates]
        top_score = candidate_scores[0] if candidate_scores else 0.0
        second_score = candidate_scores[1] if len(candidate_scores) > 1 else 0.0
        score_gap = top_score - second_score if len(candidate_scores) > 1 else 0.0

        event = CapabilitySelectionEvent(
            request_text=request_text,
            session_id=session_id,
            candidate_ids=candidate_ids,
            candidate_scores=candidate_scores,
            top_score=top_score,
            score_gap=score_gap,
            candidate_count=len(candidates),
            interaction_type=interaction_type,
        )

        with self._lock:
            self._events.append(event)

        logger.info(
            "capability_match_event",
            extra={
                "event_id": event.event_id,
                "request_text": request_text,
                "session_id": session_id,
                "candidate_ids": candidate_ids,
                "candidate_scores": candidate_scores,
                "top_score": top_score,
                "score_gap": score_gap,
                "candidate_count": len(candidates),
                "interaction_type": interaction_type,
            },
        )

        return event

    def record_user_action(
        self,
        event_id: str,
        user_action: str,
        selected_capability_id: str | None = None,
    ) -> None:
        """Record the user's eventual action on a previously presented candidate set."""
        with self._lock:
            for event in self._events:
                if event.event_id == event_id:
                    event.user_action = user_action
                    event.selected_capability_id = selected_capability_id
                    break

        logger.info(
            "capability_user_action",
            extra={
                "event_id": event_id,
                "user_action": user_action,
                "selected_capability_id": selected_capability_id,
            },
        )

    def get_events(self) -> list[CapabilitySelectionEvent]:
        """Return a copy of all recorded events."""
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        """Clear all recorded events. Primarily for testing."""
        with self._lock:
            self._events.clear()
