"""
Workflow Engine DEV-STUB (local only — never deploy to production).

Implements the contract in `../contract/workflow-engine.yaml` so the VS Code
plugin can be developed and tested before the real Workflow Engine service
exists. It reuses the existing workflow-runner (`agentic/src/workflow-runner`)
to execute workflows synchronously and replays results as SSE.

The real production execution path runs server-side in the sandboxed Agent
Execution Environment; this stub only exists for local development.

Usage (from this directory):
    ../.venv/bin/python server.py 8000
then set `workflowRunner.engineUrl` to http://127.0.0.1:8000 in VS Code.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_RUNNER = _REPO / "agentic" / "src" / "workflow-runner"
sys.path.insert(0, str(_RUNNER))

# Prefer the runner's own virtualenv packages (pydantic, pyyaml).
_venv = _RUNNER / ".venv"
if _venv.exists():
    for site in (_venv / "lib").rglob("site-packages"):
        if site.is_dir():
            sys.path.insert(0, str(site))

from executor import execute_workflow_from_file  # noqa: E402
from loader import WorkflowLoadError, load_workflow  # noqa: E402

WORKFLOWS_DIR = _REPO / "agentic" / "docs" / "workflows"

RUNS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()


def _scan_summaries() -> list[dict]:
    out: list[dict] = []
    if not WORKFLOWS_DIR.exists():
        return out
    for f in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        try:
            wf = load_workflow(f)
        except WorkflowLoadError:
            continue
        out.append(
            {
                "ref": str(f.relative_to(_REPO)),
                "name": wf.name,
                "description": wf.description,
                "role": wf.role or [],
                "inputs": wf.inputs or [],
                "outputs": wf.outputs or [],
            }
        )
    return out


def _resolve_path(ref: str) -> Path:
    candidates = [
        Path(ref),
        _REPO / ref,
        WORKFLOWS_DIR / ref,
    ]
    for c in candidates:
        if c.exists():
            return c
    return WORKFLOWS_DIR / ref


def _run(ref: str, inputs: dict | None) -> dict:
    result = execute_workflow_from_file(
        str(_resolve_path(ref)), initial_context=inputs or None
    )
    return result


def _to_status(r: dict) -> dict:
    return {
        "run_id": r.get("workflow_id"),
        "workflow_ref": r.get("workflow_path"),
        "workflow_name": r.get("workflow_name"),
        "status": r.get("status"),
        "current_step": r.get("completed_steps", 0),
        "total_steps": r.get("total_steps", 0),
        "step_results": r.get("step_results", []),
        "outputs": r.get("context"),
        "error": r.get("error"),
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence default logging
        pass

    def _send_json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/workflows" or self.path.startswith("/workflows?"):
            self._send_json(200, _scan_summaries())
        elif self.path.startswith("/workflows/") and self.path.endswith("/events"):
            run_id = self.path[len("/workflows/") : -len("/events")]
            self._sse(run_id)
        elif self.path.startswith("/workflows/"):
            run_id = self.path[len("/workflows/") :]
            with RUNS_LOCK:
                r = RUNS.get(run_id)
            if r is None:
                self._send_json(404, {"error": "unknown run_id"})
            else:
                self._send_json(200, _to_status(r))
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}

        if self.path == "/workflows/run":
            try:
                result = _run(payload.get("workflow_ref", ""), payload.get("inputs", {}))
            except Exception as e:  # noqa: BLE001
                self._send_json(400, {"error": str(e)})
                return
            run_id = result.get("workflow_id")
            with RUNS_LOCK:
                RUNS[run_id] = result
            self._send_json(202, {"run_id": run_id, "status": result.get("status", "running")})
        elif self.path == "/workflows/validate":
            try:
                ref = payload.get("workflow_ref", "")
                wf = load_workflow(_resolve_path(ref))
                self._send_json(
                    200,
                    {
                        "is_workflow": True,
                        "name": wf.name,
                        "role": wf.role or [],
                        "inputs": wf.inputs or [],
                        "outputs": wf.outputs or [],
                    },
                )
            except WorkflowLoadError as e:
                self._send_json(200, {"is_workflow": False, "reason": str(e)})
            except Exception as e:  # noqa: BLE001
                self._send_json(200, {"is_workflow": False, "reason": str(e)})
        elif self.path.startswith("/workflows/") and self.path.endswith("/stop"):
            run_id = self.path[len("/workflows/") : -len("/stop")]
            self._send_json(202, {"run_id": run_id, "stopped": True})
        else:
            self._send_json(404, {"error": "not found"})

    def _sse(self, run_id: str) -> None:
        with RUNS_LOCK:
            r = RUNS.get(run_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if r is None:
            self.wfile.write(
                b"data: "
                + json.dumps(
                    {"type": "WorkflowFailed", "run_id": run_id, "error": "unknown run_id"}
                ).encode()
                + b"\n\n"
            )
            return
        steps = r.get("step_results") or []
        total = r.get("total_steps", len(steps))
        for i, st in enumerate(steps):
            ev = {
                "type": "WorkflowProgress",
                "run_id": run_id,
                "current_step": i + 1,
                "total_steps": total,
                "step": st,
            }
            self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
        if r.get("status") == "failed":
            self.wfile.write(
                b"data: "
                + json.dumps(
                    {"type": "WorkflowFailed", "run_id": run_id, "error": r.get("error")}
                ).encode()
                + b"\n\n"
            )
        else:
            self.wfile.write(
                b"data: "
                + json.dumps(
                    {"type": "WorkflowCompleted", "run_id": run_id, "outputs": r.get("context")}
                ).encode()
                + b"\n\n"
            )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    print(f"Workflow Engine dev-stub listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
