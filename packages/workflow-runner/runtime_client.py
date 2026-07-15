"""
LangGraph Runtime Client — implements the Runtime Interface for LangGraph.

The Runtime Interface methods (start/send/add/drop/run/exit) are defined in
technical-design.md. This module adapts them to the LangGraph HTTP API
running at LANGGRAPH_URL (default http://langgraph:8000).

LangGraph API endpoints used:
- POST /threads — create a new thread (start)
- POST /threads/{thread_id}/runs — create a run on a thread (send/run)
- POST /threads/{thread_id}/runs/{run_id}/wait — block until completion
- GET /threads/{thread_id}/runs — list runs for status checks
- POST /threads/{thread_id}/runs/{run_id}/cancel — cancel a running run (stop)
- DELETE /threads/{thread_id} — delete a thread (exit)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import httpx

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://langgraph:8000")
LANGGRAPH_TIMEOUT = float(os.getenv("LANGGRAPH_TIMEOUT", "300"))
LANGGRAPH_RETRIES = int(os.getenv("LANGGRAPH_RETRIES", "3"))


class RuntimeClientError(Exception):
    """Raised when the LangGraph runtime returns an error."""
    pass


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{LANGGRAPH_URL}{path}"
    for attempt in range(1, LANGGRAPH_RETRIES + 1):
        try:
            with httpx.Client(timeout=LANGGRAPH_TIMEOUT) as client:
                resp = client.post(url, json=payload or {}, headers=_headers())
                resp.raise_for_status()
                if resp.status_code == 204:
                    return {}
                return resp.json()
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if attempt == LANGGRAPH_RETRIES:
                raise RuntimeClientError(f"LangGraph request failed: {exc}") from exc
            time.sleep(2 ** attempt)
    return {}


def _get(path: str) -> Dict[str, Any]:
    url = f"{LANGGRAPH_URL}{path}"
    try:
        with httpx.Client(timeout=LANGGRAPH_TIMEOUT) as client:
            resp = client.get(url, headers=_headers())
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPStatusError, httpx.TransportError) as exc:
        raise RuntimeClientError(f"LangGraph GET request failed: {exc}") from exc


def start() -> str:
    """Start a new runtime execution context.

    Creates a new thread in LangGraph and returns the execution id (thread_id).

    Returns:
        str: The execution id (thread id).
    """
    data = _post("/threads")
    thread_id = data.get("thread_id")
    if not thread_id:
        raise RuntimeClientError("LangGraph did not return a thread_id")
    return thread_id


def run(prompt: str, execution_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute a prompt in the LangGraph runtime.

    If execution_id is provided, the prompt is sent to the existing thread.
    Otherwise a new thread is created for this single run.

    Args:
        prompt: The composed prompt to execute.
        execution_id: Optional existing thread id to reuse.

    Returns:
        dict with keys: status, output, error, usage (tokens, etc.)
    """
    if execution_id is None:
        # Stateless single run via thread create + run + wait
        thread_id = start()
        try:
            run_id = _create_run(thread_id, prompt)
            result = await_run(thread_id, run_id)
            result["execution_id"] = thread_id
            return result
        except Exception:
            exit(thread_id)
            raise

    run_id = _create_run(execution_id, prompt)
    return await_run(execution_id, run_id)


def _create_run(thread_id: str, prompt: str) -> str:
    payload = {
        "input": {"prompt": prompt},
        "config": {
            "tags": ["workflow-engine", "skill-step"],
            "metadata": {"workflow_engine": True},
        },
    }
    data = _post(f"/threads/{thread_id}/runs", payload)
    run_id = data.get("run_id")
    if not run_id:
        raise RuntimeClientError("LangGraph did not return a run_id")
    return run_id


def await_run(thread_id: str, run_id: str) -> Dict[str, Any]:
    """Poll/wait for a run to complete.

    Uses /wait if available, otherwise polls /runs/{run_id}.
    """
    # Try the convenience wait endpoint first
    try:
        data = _post(f"/threads/{thread_id}/runs/{run_id}/wait", {"raise_error": True})
        return _normalise_run_output(data)
    except RuntimeClientError:
        pass

    # Poll fallback
    for _ in range(int(LANGGRAPH_TIMEOUT)):
        status_data = _get(f"/threads/{thread_id}/runs")
        runs = status_data.get("runs", [])
        run = next((r for r in runs if r.get("run_id") == run_id), None)
        if run is None:
            time.sleep(1)
            continue
        if run.get("status") in ("success", "completed"):
            return _normalise_run_output(run)
        if run.get("status") in ("error", "failed"):
            return {
                "status": "failed",
                "error": run.get("error", "Unknown LangGraph error"),
                "output": run.get("output"),
            }
        if run.get("status") in ("cancelled", "interrupted"):
            return {"status": "failed", "error": "Run was cancelled"}
        time.sleep(1)

    return {"status": "failed", "error": "LangGraph run timed out"}


def _normalise_run_output(data: Dict[str, Any]) -> Dict[str, Any]:
    status = data.get("status", "unknown")
    if status in ("success", "completed"):
        return {
            "status": "completed",
            "output": data.get("output"),
            "usage": data.get("usage", {}),
        }
    if status in ("error", "failed"):
        return {
            "status": "failed",
            "error": data.get("error", "Unknown LangGraph error"),
            "output": data.get("output"),
        }
    return {"status": "unknown", "output": data}


def send(message: str, execution_id: str) -> Dict[str, Any]:
    """Send a follow-up message to a running execution context.

    Args:
        message: The message to send.
        execution_id: The thread id to send to.

    Returns:
        dict with the run result.
    """
    run_id = _create_run(execution_id, message)
    return await_run(execution_id, run_id)


def add(execution_id: str, files: list[str]) -> Dict[str, Any]:
    """Add files to a runtime execution context.

    Args:
        execution_id: The thread id.
        files: List of file paths or content strings to add.

    Returns:
        dict with status.
    """
    payload = {
        "input": {
            "command": "add",
            "args": {"files": files},
        }
    }
    try:
        _post(f"/threads/{execution_id}/runs", payload)
        return {"status": "completed"}
    except RuntimeClientError as exc:
        return {"status": "failed", "error": str(exc)}


def drop(execution_id: str, files: list[str]) -> Dict[str, Any]:
    """Remove files from a runtime execution context.

    Args:
        execution_id: The thread id.
        files: List of file paths to drop.

    Returns:
        dict with status.
    """
    payload = {
        "input": {
            "command": "drop",
            "args": {"files": files},
        }
    }
    try:
        _post(f"/threads/{execution_id}/runs", payload)
        return {"status": "completed"}
    except RuntimeClientError as exc:
        return {"status": "failed", "error": str(exc)}


def stop(execution_id: str, run_id: str) -> Dict[str, Any]:
    """Stop a running execution.

    Args:
        execution_id: The thread id.
        run_id: The run id to cancel.

    Returns:
        dict with status.
    """
    try:
        _post(f"/threads/{execution_id}/runs/{run_id}/cancel", {})
        return {"status": "stopped"}
    except RuntimeClientError as exc:
        return {"status": "failed", "error": str(exc)}


def exit(execution_id: str) -> Dict[str, Any]:
    """Clean up a runtime execution context.

    Deletes the thread.

    Args:
        execution_id: The thread id to delete.

    Returns:
        dict with status.
    """
    try:
        url = f"{LANGGRAPH_URL}/threads/{execution_id}"
        with httpx.Client(timeout=LANGGRAPH_TIMEOUT) as client:
            resp = client.delete(url, headers=_headers())
            resp.raise_for_status()
        return {"status": "exited"}
    except (httpx.HTTPStatusError, httpx.TransportError) as exc:
        return {"status": "failed", "error": str(exc)}


def get_status(execution_id: str) -> Dict[str, Any]:
    """Get the current status of a runtime execution context.

    Args:
        execution_id: The thread id.

    Returns:
        dict with run statuses.
    """
    try:
        return _get(f"/threads/{execution_id}/runs")
    except RuntimeClientError as exc:
        return {"status": "failed", "error": str(exc)}
