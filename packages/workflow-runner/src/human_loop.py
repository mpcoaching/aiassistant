"""
Human-in-the-loop session support (Phase 6).

Extends Session to support pause/resume for human input without AI tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HumanInputStatus(str, Enum):
    NONE = "none"
    REQUESTED = "requested"
    RECEIVED = "received"
    APPLIED = "applied"


class HumanInputRequest(BaseModel):
    request_id: str
    question: str
    context: Dict[str, Any] = Field(default_factory=dict)
    options: List[str] = Field(default_factory=list)
    status: HumanInputStatus = HumanInputStatus.REQUESTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    response: Optional[str] = None
    responded_at: Optional[datetime] = None


class HumanInTheLoopMixin:
    """Mixin for Session to support human-in-the-loop pauses."""

    def __init__(self) -> None:
        self._pending_human_input: Optional[HumanInputRequest] = None
        self._human_input_history: List[HumanInputRequest] = []

    def request_human_input(self, question: str, context: Dict[str, Any] = None, options: List[str] = None) -> HumanInputRequest:
        """Pause execution and request human input."""
        request = HumanInputRequest(
            request_id=f"human-{datetime.now(timezone.utc).timestamp()}",
            question=question,
            context=context or {},
            options=options or [],
            status=HumanInputStatus.REQUESTED,
        )
        self._pending_human_input = request
        self._human_input_history.append(request)
        return request

    def provide_human_input(self, request_id: str, response: str) -> HumanInputRequest:
        """Record human response and clear the pending request."""
        if self._pending_human_input is None or self._pending_human_input.request_id != request_id:
            raise ValueError(f"No pending human input request with id {request_id}")

        self._pending_human_input.response = response
        self._pending_human_input.responded_at = datetime.now(timezone.utc)
        self._pending_human_input.status = HumanInputStatus.RECEIVED
        completed = self._pending_human_input
        self._pending_human_input = None
        return completed

    def has_pending_human_input(self) -> bool:
        return self._pending_human_input is not None and self._pending_human_input.status == HumanInputStatus.REQUESTED

    def get_pending_human_input(self) -> Optional[HumanInputRequest]:
        return self._pending_human_input

    def apply_human_response_to_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the latest human response to the session context."""
        last_human = self._human_input_history[-1] if self._human_input_history else None
        if last_human and last_human.response:
            context = dict(context)
            context["human_response"] = last_human.response
            context["human_response_at"] = last_human.responded_at.isoformat()
            last_human.status = HumanInputStatus.APPLIED
            if self._pending_human_input and self._pending_human_input.request_id == last_human.request_id:
                self._pending_human_input = None
        return context
