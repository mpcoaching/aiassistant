#!/usr/bin/env python3
"""Paperclip process adapter for the Assistant agent.

This script is executed by Paperclip's process adapter when the Assistant
agent is triggered (via heartbeat/wakeup). It:

1. Reads Paperclip runtime env vars
2. Fetches the heartbeat run context to discover the associated issue
3. Fetches the issue to get the user message
4. Calls the existing AI runtime (via HTTP) to generate a response
5. Emits a JSON result to stdout for Paperclip to capture

The script intentionally uses only the Python standard library so that
Paperclip can execute it without installing our monorepo dependencies.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


PAPERCLIP_API_URL = os.environ.get("PAPERCLIP_API_URL", "http://localhost:3101")
PAPERCLIP_API_KEY = os.environ.get("PAPERCLIP_API_KEY", "")
PAPERCLIP_RUN_ID = os.environ.get("PAPERCLIP_RUN_ID", "")
AI_RUNTIME_URL = os.environ.get("AI_RUNTIME_URL", "http://localhost:8000/assistant/chat")


def _paperclip_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if PAPERCLIP_API_KEY:
        headers["Authorization"] = f"Bearer {PAPERCLIP_API_KEY}"
    return headers


def _paperclip_get(path: str) -> dict[str, object]:
    url = f"{PAPERCLIP_API_URL.rstrip('/')}{path}"
    req = urllib.request.Request(url, headers=_paperclip_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(json.dumps({"error": f"Paperclip API error {exc.code}: {exc.reason}", "path": path}))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"error": f"Paperclip request failed: {exc}", "path": path}))
        sys.exit(1)


def _ai_generate(message: str, session_id: str | None = None) -> dict[str, object]:
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        AI_RUNTIME_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        return {"error": f"AI runtime error {exc.code}: {body}", "message": ""}
    except Exception as exc:
        return {"error": f"AI runtime request failed: {exc}", "message": ""}


def main() -> None:
    if not PAPERCLIP_RUN_ID:
        print(json.dumps({"error": "PAPERCLIP_RUN_ID is not set"}))
        sys.exit(1)

    run = _paperclip_get(f"/api/heartbeat-runs/{PAPERCLIP_RUN_ID}")
    context = run.get("contextSnapshot") or {}
    issue_id = context.get("issueId")

    message = ""
    session_id = None
    if issue_id:
        issue = _paperclip_get(f"/api/issues/{issue_id}")
        title = issue.get("title") or ""
        if title.startswith("chat:"):
            session_id = title[len("chat:"):]
        message = issue.get("description") or title or ""
    else:
        message = context.get("paperclipTaskMarkdown") or "Hello"

    if not message:
        print(json.dumps({"response": "I received an empty task.", "model": None}))
        return

    ai_result = _ai_generate(message, session_id)
    response_text = ai_result.get("message") or ai_result.get("error") or ""
    telemetry = ai_result.get("telemetry") or {}

    result = {
        "response": response_text,
        "model": telemetry.get("ai_model"),
        "latencyMs": telemetry.get("ai_latency_ms"),
        "aiInvoked": telemetry.get("ai_invoked"),
        "aiSuccess": telemetry.get("ai_success"),
        "runId": PAPERCLIP_RUN_ID,
        "agentId": run.get("agentId"),
        "issueId": issue_id,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
