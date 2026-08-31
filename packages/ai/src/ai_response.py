"""
AI Response Service — calls Portkey for real LLM-generated responses.

Reads configuration from environment variables:
  PORTKEY_MASTER_KEY — required, used as x-portkey-api-key
  PORTKEY_BASE_URL  — optional, defaults to http://localhost:4000
  AI_PROVIDER       — optional, defaults to groq
  AI_MODEL          — optional, defaults to qwen/qwen3.8-27b
  GROQ_API_KEY      — optional, Groq provider key
  OPENROUTER_API_KEY — optional, OpenRouter provider key
  GEMINI_API_KEY    — optional, Gemini provider key
  GITHUB_PAT        — optional, GitHub Models provider key
  HF_API_KEY        — optional, HuggingFace provider key
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("ai.ai_response")

_PROVIDER_API_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "github": "GITHUB_PAT",
    "huggingface": "HF_API_KEY",
}


class AIResponseService:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("PORTKEY_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.api_key = api_key or os.getenv("PORTKEY_MASTER_KEY", "")
        self.provider = provider or os.getenv("AI_PROVIDER", "groq")
        self.model = model or os.getenv("AI_MODEL", "qwen/qwen3.8-27b")
        self._client = httpx.Client(timeout=60.0)

        if not self.api_key:
            raise ValueError("PORTKEY_MASTER_KEY is required for AIResponseService")

    def _headers(self) -> dict[str, str]:
        return {
            "x-portkey-api-key": self.api_key,
            "Content-Type": "application/json",
            "x-portkey-config": json.dumps(self._portkey_config()),
        }

    def _portkey_config(self) -> dict[str, Any]:
        targets: list[dict[str, Any]] = []
        provider_key = self._provider_api_key()
        if provider_key:
            targets.append(
                {
                    "provider": self.provider,
                    "api_key": provider_key,
                    "override_params": {"model": self.model},
                }
            )
        return {
            "strategy": {"mode": "fallback"},
            "retry": {"attempts": 3, "on_status_codes": [429, 500, 502, 503, 504]},
            "request_timeout": 30000,
            "targets": targets,
        }

    def _provider_api_key(self) -> str | None:
        env_var = _PROVIDER_API_KEY_ENV.get(self.provider)
        if env_var:
            return os.getenv(env_var)
        return None

    def generate(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        messages: list[dict[str, str]] = []
        if context:
            system_prompt = self._build_system_prompt(context)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        start = time.perf_counter()
        try:
            response = self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
            response = self._handle_rate_limit(response, messages)
            response.raise_for_status()
            data = response.json()
            latency_ms = int((time.perf_counter() - start) * 1000)
            telemetry = {
                "ai_invoked": True,
                "ai_model": self.model,
                "ai_latency_ms": latency_ms,
                "ai_success": True,
                "ai_error": None,
            }
            return data["choices"][0]["message"]["content"], telemetry
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("AI response generation failed: %s", exc)
            telemetry = {
                "ai_invoked": True,
                "ai_model": self.model,
                "ai_latency_ms": latency_ms,
                "ai_success": False,
                "ai_error": str(exc),
            }
            raise

    def _handle_rate_limit(self, response: httpx.Response, messages: list[dict[str, str]]) -> httpx.Response:
        max_retries = 3
        for attempt in range(max_retries):
            if response.status_code != 429:
                return response
            retry_after = self._parse_retry_after(response)
            wait = retry_after if retry_after > 0 else 2 ** attempt
            logger.warning("Rate limited (attempt %d/%d), retrying after %.1fs", attempt + 1, max_retries, wait)
            time.sleep(wait)
            response = self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
        return response

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        try:
            import json
            body = json.loads(response.text)
            msg = body.get("error", {}).get("message", "")
            if "Please retry in" in msg:
                return float(msg.split("Please retry in")[1].split("s")[0].strip())
        except Exception:
            pass
        return 1.0

    @staticmethod
    def _build_system_prompt(context: dict[str, Any]) -> str | None:
        parts = []
        if context.get("planning_context"):
            parts.append(f"Planning context: {context['planning_context']}")
        if context.get("analysis_context"):
            parts.append(f"Analysis context: {context['analysis_context']}")
        return "\n".join(parts) if parts else None

    def classify_actionable_intent(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        accumulated_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_prompt = (
            "You are an intent classifier for a business assistant. "
            "Given the conversation history and the current user message, "
            "determine whether the user is transitioning from conversation to taking action.\n\n"
            "Respond with ONLY valid JSON in this exact format:\n"
            '{"mode": "conversational" | "actionable", "action": "investigate" | "analyse" | "plan" | null, '
            '"objective": "string" | null, "context": {} | null, "confidence": "high" | "medium" | "low"}\n\n'
            "Rules:\n"
            '- mode="actionable" only when the user is clearly requesting the system to DO something.\n'
            '- mode="conversational" for general questions, discussion, exploration, or clarification.\n'
            '- action should be one of: investigate, analyse, plan.\n'
            '- objective should capture the specific goal in one sentence.\n'
            '- context should preserve relevant facts from the conversation as key-value pairs.\n'
            '- confidence should reflect how certain you are.\n'
            '- If mode="conversational", action, objective, and context can be null/empty.\n'
            "- Do NOT include any text outside the JSON object."
        )
        history_text = ""
        if conversation_history:
            for turn in conversation_history:
                history_text += f"{turn['role']}: {turn['content']}\n"
        context_text = ""
        if accumulated_context:
            context_text = f"\nAccumulated context: {accumulated_context}"

        messages = [{"role": "system", "content": system_prompt}]
        if history_text:
            messages.append({"role": "user", "content": f"Conversation history:\n{history_text}"})
        messages.append({"role": "user", "content": f"Current message: {user_message}{context_text}"})

        start = time.perf_counter()
        try:
            response = self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
            response = self._handle_rate_limit(response, messages)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            import json

            result = json.loads(content)
            result.setdefault("mode", "conversational")
            result.setdefault("action", None)
            result.setdefault("objective", None)
            result.setdefault("context", {})
            result.setdefault("confidence", "low")
            return result
        except Exception as exc:
            logger.debug("Actionable intent classification failed: %s", exc)
            return {"mode": "conversational", "action": None, "objective": None, "context": {}, "confidence": "low"}
