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

import time
from typing import Any

import httpx
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration


class RuntimeClientError(Exception):
    """Raised when the LangGraph runtime returns an error."""


class RuntimeClient:
    def __init__(self, langgraph: LangGraphRuntimeConfiguration) -> None:
        self._url = langgraph.url
        self._timeout_seconds = langgraph.timeout_seconds
        self._retries = langgraph.retries

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._url}{path}"
        for attempt in range(1, self._retries + 1):
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    resp = client.post(url, json=payload or {}, headers=self._headers())
                    resp.raise_for_status()
                    if resp.status_code == 204:
                        return {}
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                if attempt == self._retries:
                    raise RuntimeClientError(f"LangGraph request failed: {exc}") from exc
                time.sleep(2 ** attempt)
        return {}

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self._url}{path}"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                resp = client.get(url, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            raise RuntimeClientError(f"LangGraph GET request failed: {exc}") from exc

    def start(self) -> str:
        data = self._post("/threads")
        thread_id = data.get("thread_id")
        if not thread_id:
            raise RuntimeClientError("LangGraph did not return a thread_id")
        return thread_id

    def run(self, prompt: str, execution_id: str | None = None) -> dict[str, Any]:
        if execution_id is None:
            thread_id = self.start()
            try:
                run_id = self._create_run(thread_id, prompt)
                result = self._await_run(thread_id, run_id)
                result["execution_id"] = thread_id
                return result
            except Exception:
                self.exit(thread_id)
                raise

        run_id = self._create_run(execution_id, prompt)
        return self._await_run(execution_id, run_id)

    def _create_run(self, thread_id: str, prompt: str) -> str:
        payload = {
            "input": {"prompt": prompt},
            "config": {
                "tags": ["workflow-engine", "skill-step"],
                "metadata": {"workflow_engine": True},
            },
        }
        data = self._post(f"/threads/{thread_id}/runs", payload)
        run_id = data.get("run_id")
        if not run_id:
            raise RuntimeClientError("LangGraph did not return a run_id")
        return run_id

    def _await_run(self, thread_id: str, run_id: str) -> dict[str, Any]:
        try:
            data = self._post(f"/threads/{thread_id}/runs/{run_id}/wait", {"raise_error": True})
            return self._normalise_run_output(data)
        except RuntimeClientError:
            pass

        for _ in range(int(self._timeout_seconds)):
            status_data = self._get(f"/threads/{thread_id}/runs")
            runs = status_data.get("runs", [])
            run = next((r for r in runs if r.get("run_id") == run_id), None)
            if run is None:
                time.sleep(1)
                continue
            if run.get("status") in ("success", "completed"):
                return self._normalise_run_output(run)
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

    def _normalise_run_output(self, data: dict[str, Any]) -> dict[str, Any]:
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

    def send(self, message: str, execution_id: str) -> dict[str, Any]:
        run_id = self._create_run(execution_id, message)
        return self._await_run(execution_id, run_id)

    def add(self, execution_id: str, files: list[str]) -> dict[str, Any]:
        payload = {
            "input": {
                "command": "add",
                "args": {"files": files},
            }
        }
        try:
            self._post(f"/threads/{execution_id}/runs", payload)
            return {"status": "completed"}
        except RuntimeClientError as exc:
            return {"status": "failed", "error": str(exc)}

    def drop(self, execution_id: str, files: list[str]) -> dict[str, Any]:
        payload = {
            "input": {
                "command": "drop",
                "args": {"files": files},
            }
        }
        try:
            self._post(f"/threads/{execution_id}/runs", payload)
            return {"status": "completed"}
        except RuntimeClientError as exc:
            return {"status": "failed", "error": str(exc)}

    def stop(self, execution_id: str, run_id: str) -> dict[str, Any]:
        try:
            self._post(f"/threads/{execution_id}/runs/{run_id}/cancel", {})
            return {"status": "stopped"}
        except RuntimeClientError as exc:
            return {"status": "failed", "error": str(exc)}

    def exit(self, execution_id: str) -> dict[str, Any]:
        try:
            url = f"{self._url}/threads/{execution_id}"
            with httpx.Client(timeout=self._timeout_seconds) as client:
                resp = client.delete(url, headers=self._headers())
                resp.raise_for_status()
            return {"status": "exited"}
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            return {"status": "failed", "error": str(exc)}

    def get_status(self, execution_id: str) -> dict[str, Any]:
        try:
            return self._get(f"/threads/{execution_id}/runs")
        except RuntimeClientError as exc:
            return {"status": "failed", "error": str(exc)}


_default_client: RuntimeClient | None = None


def configure(langgraph: LangGraphRuntimeConfiguration) -> None:
    global _default_client
    _default_client = RuntimeClient(langgraph)


def _get_default_client() -> RuntimeClient:
    if _default_client is None:
        raise RuntimeError("RuntimeClient not configured")
    return _default_client


def start() -> str:
    return _get_default_client().start()


def run(prompt: str, execution_id: str | None = None) -> dict[str, Any]:
    return _get_default_client().run(prompt, execution_id)


def send(message: str, execution_id: str) -> dict[str, Any]:
    return _get_default_client().send(message, execution_id)


def add(execution_id: str, files: list[str]) -> dict[str, Any]:
    return _get_default_client().add(execution_id, files)


def drop(execution_id: str, files: list[str]) -> dict[str, Any]:
    return _get_default_client().drop(execution_id, files)


def stop(execution_id: str, run_id: str) -> dict[str, Any]:
    return _get_default_client().stop(execution_id, run_id)


def exit(execution_id: str) -> dict[str, Any]:
    return _get_default_client().exit(execution_id)


def get_status(execution_id: str) -> dict[str, Any]:
    return _get_default_client().get_status(execution_id)