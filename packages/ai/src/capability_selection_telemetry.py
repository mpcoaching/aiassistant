"""
Increment 21K — Capability selection telemetry.

Records observational events for capability matching and selection
without changing production behaviour or introducing new infrastructure.

This module is strictly measurement-only. It does not modify matching,
decision policy, execution, or response behaviour.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections import defaultdict
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

    def __init__(self, persistence_path: str | None = None) -> None:
        self._events: list[CapabilitySelectionEvent] = []
        self._lock = threading.Lock()
        self._persistence_path = persistence_path
        self._session_events: dict[str, list[CapabilitySelectionEvent]] = defaultdict(list)
        self._reformulation_candidates: dict[str, list[CapabilitySelectionEvent]] = defaultdict(list)

        if persistence_path:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load events from persistent storage."""
        if not self._persistence_path or not os.path.exists(self._persistence_path):
            return

        try:
            with open(self._persistence_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    event = CapabilitySelectionEvent(
                        event_id=data["event_id"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        request_text=data.get("request_text", ""),
                        session_id=data.get("session_id"),
                        candidate_ids=data.get("candidate_ids", []),
                        candidate_scores=data.get("candidate_scores", []),
                        top_score=data.get("top_score", 0.0),
                        score_gap=data.get("score_gap", 0.0),
                        candidate_count=data.get("candidate_count", 0),
                        interaction_type=data.get("interaction_type", "select"),
                        user_action=data.get("user_action"),
                        selected_capability_id=data.get("selected_capability_id"),
                    )
                    self._events.append(event)
                    if event.session_id:
                        self._session_events[event.session_id].append(event)
        except Exception as exc:
            logger.warning("Failed to load telemetry from disk: %s", exc)

    def _persist_event(self, event: CapabilitySelectionEvent) -> None:
        """Append event to persistent storage."""
        if not self._persistence_path:
            return

        try:
            os.makedirs(os.path.dirname(self._persistence_path), exist_ok=True)
            with open(self._persistence_path, "a", encoding="utf-8") as f:
                data = {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "request_text": event.request_text,
                    "session_id": event.session_id,
                    "candidate_ids": event.candidate_ids,
                    "candidate_scores": event.candidate_scores,
                    "top_score": event.top_score,
                    "score_gap": event.score_gap,
                    "candidate_count": event.candidate_count,
                    "interaction_type": event.interaction_type,
                    "user_action": event.user_action,
                    "selected_capability_id": event.selected_capability_id,
                }
                f.write(json.dumps(data) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist telemetry event: %s", exc)

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
            if session_id:
                self._session_events[session_id].append(event)

        self._persist_event(event)

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
        updated_event = None
        with self._lock:
            for event in self._events:
                if event.event_id == event_id:
                    event.user_action = user_action
                    event.selected_capability_id = selected_capability_id
                    updated_event = event
                    break

        if updated_event is not None:
            self._persist_event(updated_event)

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

    def get_events_by_session(self, session_id: str) -> list[CapabilitySelectionEvent]:
        """Return events for a specific session."""
        with self._lock:
            return list(self._session_events.get(session_id, []))

    def get_reformulation_candidates(self) -> list[CapabilitySelectionEvent]:
        """Return events that are potential reformulations.
        
        A reformulation candidate is an event in a session that has multiple
        capability selection events, suggesting the user re-queried after
        seeing candidates.
        """
        with self._lock:
            reformulations = []
            for session_id, events in self._session_events.items():
                if len(events) > 1:
                    reformulations.extend(events)
            return reformulations

    def clear(self) -> None:
        """Clear all recorded events. Primarily for testing."""
        with self._lock:
            self._events.clear()
            self._session_events.clear()
            self._reformulation_candidates.clear()

    def export_to_json(self, output_path: str) -> None:
        """Export all events to a JSON file."""
        with self._lock:
            events_data = []
            for event in self._events:
                events_data.append({
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "request_text": event.request_text,
                    "session_id": event.session_id,
                    "candidate_ids": event.candidate_ids,
                    "candidate_scores": event.candidate_scores,
                    "top_score": event.top_score,
                    "score_gap": event.score_gap,
                    "candidate_count": event.candidate_count,
                    "interaction_type": event.interaction_type,
                    "user_action": event.user_action,
                    "selected_capability_id": event.selected_capability_id,
                })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(events_data, f, indent=2)
