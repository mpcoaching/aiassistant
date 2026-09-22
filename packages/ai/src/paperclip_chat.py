"""
Paperclip-managed chat service.

Routes conversational requests through Paperclip so that the Assistant
agent is a real Paperclip-managed role/agent, rather than our application
pretending to be its own organisational control plane.

Preferred path:
  User message
    → Paperclip issue assigned to Assistant agent
      → Paperclip heartbeat execution
        → process adapter script
          → existing AI runtime
            → Portkey
              → real LLM
            ← LLM response
          ← AI runtime response
        ← Paperclip captures resultJson
      ← heartbeat run completes
    ← PaperclipChatService returns ChatResponse

Architectural boundary:
  - Paperclip owns: agent identity, work, execution, accountability
  - Our AI runtime owns: model invocation, Portkey, AI telemetry
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from chat import ChatResponse

from organisation_paperclip import PaperclipOrganisationControlPlane

logger = logging.getLogger("ai.paperclip_chat")

PAPERCLIP_ASSISTANT_AGENT_ID = os.getenv("PAPERCLIP_ASSISTANT_AGENT_ID", "")
PAPERCLIP_POLL_INTERVAL_SECONDS = float(os.getenv("PAPERCLIP_POLL_INTERVAL_SECONDS", "2.0"))
PAPERCLIP_POLL_MAX_ATTEMPTS = int(os.getenv("PAPERCLIP_POLL_MAX_ATTEMPTS", "30"))


class PaperclipChatService:
    """Chat service that routes through Paperclip-managed Assistant agent."""

    def __init__(
        self,
        org_plane: PaperclipOrganisationControlPlane | None = None,
        assistant_agent_id: str = PAPERCLIP_ASSISTANT_AGENT_ID,
    ) -> None:
        self._org_plane = org_plane
        self._assistant_agent_id = assistant_agent_id

    def chat(self, message: str, session_id: str | None = None, context: dict[str, Any] | None = None) -> ChatResponse:
        """Route a chat message through Paperclip and return the result."""
        if not self._assistant_agent_id:
            return ChatResponse(
                message="Paperclip Assistant agent is not configured.",
                session_id=session_id or "error",
                status="error",
                reasoning="PAPERCLIP_ASSISTANT_AGENT_ID is not set",
            )

        if self._org_plane is None:
            return ChatResponse(
                message="Paperclip organisational control plane is not available.",
                session_id=session_id or "error",
                status="error",
                reasoning="PaperclipOrganisationControlPlane is not configured",
            )

        session_id = session_id or f"ses-paperclip-{hash(message) & 0xFFFFFFFF}"
        work = self._find_or_create_chat_work(session_id, message)

        if work is None:
            return ChatResponse(
                message="Failed to create or locate Paperclip work.",
                session_id=session_id,
                status="error",
                reasoning="_find_or_create_chat_work returned None",
            )

        try:
            trigger_result = self._org_plane.trigger_execution(work.id, self._assistant_agent_id)
            logger.info("Triggered Paperclip execution for work %s: %s", work.id, trigger_result)
        except Exception as exc:
            logger.error("Failed to trigger Paperclip execution: %s", exc)

        completed_work = self._wait_for_execution(work.id)
        if completed_work is None:
            return ChatResponse(
                message="Paperclip execution did not complete in time.",
                session_id=session_id,
                status="timeout",
                reasoning="wait_for_execution returned None",
            )

        outcome = completed_work.outcome or {}
        response_text = ""
        model = None
        ai_invoked = None
        ai_success = None
        ai_latency_ms = None

        if isinstance(outcome, dict):
            stdout = outcome.get("stdout")
            if isinstance(stdout, str) and stdout.strip():
                try:
                    parsed = json.loads(stdout)
                    if isinstance(parsed, dict):
                        response_text = parsed.get("response", "")
                        model = parsed.get("model")
                        ai_invoked = parsed.get("aiInvoked")
                        ai_success = parsed.get("aiSuccess")
                        ai_latency_ms = parsed.get("latencyMs")
                except json.JSONDecodeError:
                    response_text = stdout

        if not response_text:
            response_text = "Paperclip execution completed but produced no response."

        telemetry = {
            "runtime": "paperclip",
            "agent_id": self._assistant_agent_id,
            "work_id": completed_work.id,
            "model": model,
            "ai_invoked": ai_invoked,
            "ai_success": ai_success,
            "ai_latency_ms": ai_latency_ms,
        }

        return ChatResponse(
            message=response_text,
            session_id=session_id,
            status="completed",
            reasoning="Generated via Paperclip-managed Assistant agent",
            telemetry=telemetry,
        )

    def _find_or_create_chat_work(self, session_id: str, message: str):
        """Find an existing chat work item for the session or create a new one."""
        chat_title = f"chat:{session_id}"
        try:
            all_work = self._org_plane.list_work()
        except Exception:
            all_work = []

        existing = None
        for w in all_work:
            if (
                getattr(w, "assignee_agent_id", None) == self._assistant_agent_id
                and getattr(w, "title", None) == chat_title
                and getattr(w, "status", None) is not None
                and w.status.value not in ("completed", "cancelled")
            ):
                existing = w
                break

        if existing is not None:
            self._org_plane.update_work(existing.id, description=message)
            return existing

        try:
            return self._org_plane.create_work(
                title=chat_title,
                description=message,
                assignee_agent_id=self._assistant_agent_id,
                priority="medium",
            )
        except Exception as exc:
            logger.error("Failed to create Paperclip work: %s", exc)
            return None

    def _wait_for_execution(self, work_id: str):
        """Poll for Paperclip execution result."""
        try:
            return self._org_plane.wait_for_execution(work_id)
        except Exception as exc:
            logger.error("wait_for_execution failed: %s", exc)
            return None
