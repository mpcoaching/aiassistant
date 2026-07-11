"""
FastAPI REST API for the Workflow Engine.

Endpoints:
  GET  /health                      — liveness probe
  GET  /workflows?path=…            — list workflow definitions
  POST /workflows/{name}/run        — trigger a workflow execution
  GET  /workflows/{id}/status       — inspect a running/completed instance
  POST /workflows/{id}/pause        — pause a running workflow
  POST /workflows/{id}/resume       — resume a paused workflow
  POST /workflows/{id}/stop         — stop a running workflow
  POST /schedules                    — create a schedule
  DELETE /schedules/{id}             — remove a schedule
  GET  /schedules                    — list active schedules
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Allow imports from the workflow-runner package directory when run as a package
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from executor import execute_workflow_from_file  # noqa: E402
from loader import load_workflow, resolve_workflow_path, resolve_skill_path, resolve_tool_path  # noqa: E402
from models import WorkflowDefinition  # noqa: E402
from db import (  # noqa: E402
    advance_step,
    create_workflow_state,
    delete_schedule,
    fail_workflow,
    load_workflow_state,
    pause_workflow,
    resume_workflow,
    stop_workflow,
)
from bus import EventBus  # noqa: E402
from scheduler import schedule_workflow, start_scheduler, shutdown_scheduler, get_scheduled_jobs, _build_scheduler  # noqa: E402

logger = logging.getLogger("workflow-engine.api")
app = FastAPI(title="Workflow Engine", version="1.0.0")

# Resolve repo root for workflow discovery
_REPO_ROOT = Path(os.getenv("REPO_ROOT", "/aiassistant"))
_WORKFLOW_PATHS = [
    _REPO_ROOT / "agentic" / "docs" / "workflows",
    _REPO_ROOT / "agentic" / "workflows",
]


def _search_paths() -> list[Path]:
    return [
        _REPO_ROOT / "agentic" / "skills",
        _REPO_ROOT / "agentic" / "docs" / "skills",
        _REPO_ROOT / "agentic" / "tools",
        _REPO_ROOT / "agentic" / "docs",
        _REPO_ROOT / "agentic" / "docs" / "workflows",
        _REPO_ROOT / "agentic" / "workflows",
    ]


def _bus() -> EventBus:
    if not hasattr(app.state, "bus"):
        app.state.bus = EventBus()
        try:
            app.state.bus.declare_topology()
        except Exception:
            logger.exception("Failed to declare bus topology")
    return app.state.bus


def _scheduler() -> "_SchedulerHolder":
    if not hasattr(app.state, "scheduler"):
        sched = _build_scheduler()
        start_scheduler(sched)
        app.state.scheduler = _SchedulerHolder(sched)
    return app.state.scheduler


class _SchedulerHolder:
    def __init__(self, scheduler: Any) -> None:
        self._scheduler = scheduler

    @property
    def sched(self) -> Any:
        return self._scheduler


# ---- Models ----

class HealthResponse(BaseModel):
    status: str


class WorkflowListItem(BaseModel):
    name: str
    description: Optional[str] = None
    path: str


class RunRequest(BaseModel):
    initial_context: Optional[Dict[str, Any]] = None
    role_override: Optional[str] = None


class ScheduleRequest(BaseModel):
    workflow_name: str = Field(..., description="Name of the workflow to schedule")
    schedule_id: str = Field(..., description="Unique id for the schedule")
    cron: str = Field(..., description="Cron expression (e.g. '0 8 * * *')")
    initial_context: Optional[Dict[str, Any]] = None
    role_override: Optional[str] = None


class ScheduleResponse(BaseModel):
    schedule_id: str
    workflow_name: str
    cron: str
    next_run_time: Optional[str] = None
    enabled: bool


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    current_step_index: int
    total_steps: int
    error: Optional[str] = None
    step_results: List[Optional[Dict[str, Any]]] = Field(default_factory=list)


# ---- Lifecycle ----

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Workflow Engine API starting up")
    try:
        bus = _bus()
        bus.start_consumers(
            workflow_requested_cb=_handle_bus_workflow_requested,
            workflow_control_cb=_handle_bus_workflow_control,
        )
    except Exception:
        logger.exception("Failed to start bus consumers")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        _scheduler()
        shutdown_scheduler(_scheduler.sched)
    except Exception:
        pass
    try:
        _bus().shutdown()
    except Exception:
        pass


# ---- Routes ----

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/workflows", response_model=List[WorkflowListItem])
async def list_workflows() -> List[WorkflowListItem]:
    items: List[WorkflowListItem] = []
    for base in _WORKFLOW_PATHS:
        if not base.exists():
            continue
        for f in sorted(base.glob("*.yaml")):
            name = f.stem
            desc: Optional[str] = None
            try:
                wf = load_workflow(str(f))
                desc = wf.description
                name = wf.name
            except Exception:
                pass
            items.append(WorkflowListItem(name=name, description=desc, path=str(f)))
    return items


@app.post("/workflows/{name}/run")
async def run_workflow(name: str, body: Optional[RunRequest] = None) -> Dict[str, Any]:
    body = body or RunRequest()
    path = resolve_workflow_path(name, _search_paths())
    if path is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    try:
        workflow = load_workflow(str(path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid workflow: {exc}") from exc

    workflow_id = str(__import__("uuid").uuid4())[:8]
    state = create_workflow_state(
        workflow_name=workflow.name,
        workflow_path=str(path),
        steps=workflow.steps,
        initial_context=body.initial_context,
    )

    bus = _bus()
    bus.publish_workflow_started(workflow_id=workflow_id, payload={
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "workflow_name": workflow.name,
        "total_steps": len(workflow.steps),
    })

    # Execute synchronously for Phase 1
    result = _execute_and_publish(workflow, str(path), state, body.initial_context, body.role_override, bus)

    return result


@app.get("/workflows/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def workflow_status(workflow_id: str, workflow_path: str) -> WorkflowStatusResponse:
    # Try to infer path if not provided by name
    if workflow_path:
        state = load_workflow_state(workflow_id, workflow_path)
    else:
        state = None
        for p in _WORKFLOW_PATHS:
            state = load_workflow_state(workflow_id, str(p))
            if state:
                break
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return WorkflowStatusResponse(
        workflow_id=state.workflow_id,
        workflow_name=state.workflow_name,
        status=state.status,
        current_step_index=state.current_step_index,
        total_steps=len(state.steps),
        error=state.error,
        step_results=state.step_results,
    )


@app.post("/workflows/{workflow_id}/pause")
async def pause_workflow_endpoint(workflow_id: str, workflow_path: str) -> Dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot pause workflow in status {state.status}")
    state = pause_workflow(state)
    _bus().publish_workflow_paused(workflow_id, {
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "paused_step_index": state.current_step_index,
        "reason": "user_requested",
    })
    return {"status": "paused", "workflow_id": workflow_id}


@app.post("/workflows/{workflow_id}/resume")
async def resume_workflow_endpoint(workflow_id: str, workflow_path: str) -> Dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume workflow in status {state.status}")
    state = resume_workflow(state)
    _bus().publish_workflow_resumed(workflow_id, {
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "resuming_step_index": state.current_step_index,
    })
    return {"status": "running", "workflow_id": workflow_id}


@app.post("/workflows/{workflow_id}/stop")
async def stop_workflow_endpoint(workflow_id: str, workflow_path: str) -> Dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status not in ("running", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot stop workflow in status {state.status}")
    state = stop_workflow(state)
    _bus().publish_workflow_stopped(workflow_id, {
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "completed_steps": state.current_step_index,
        "reason": "user_requested",
    })
    return {"status": "stopped", "workflow_id": workflow_id}


@app.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(body: ScheduleRequest) -> ScheduleResponse:
    holder = _scheduler()
    try:
        schedule_workflow(
            scheduler=holder.sched,
            schedule_id=body.schedule_id,
            workflow_name=body.workflow_name,
            cron=body.cron,
            initial_context=body.initial_context,
            role_override=body.role_override,
            publish_callback=lambda event_type, wf_id, payload: _bus().publish(event_type, wf_id, event_type, payload),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = holder.sched.get_job(body.schedule_id)
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    resp = ScheduleResponse(schedule_id=body.schedule_id, workflow_name=body.workflow_name, cron=body.cron, next_run_time=next_run, enabled=True)
    _bus().publish_schedule_created(body.schedule_id, {
        "schedule_id": body.schedule_id,
        "workflow_name": body.workflow_name,
        "cron": body.cron,
        "next_fire_time": next_run,
    })
    return resp


@app.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str) -> Dict[str, Any]:
    holder = _scheduler()
    try:
        holder.sched.remove_job(schedule_id)
    except Exception:
        pass
    _bus().publish_schedule_removed(schedule_id, {
        "schedule_id": schedule_id,
    })
    try:
        delete_schedule(schedule_id)
    except Exception:
        pass
    return {"status": "removed", "schedule_id": schedule_id}


@app.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules() -> List[ScheduleResponse]:
    holder = _scheduler()
    items: List[ScheduleResponse] = []
    for job in holder.sched.get_jobs():
        items.append(ScheduleResponse(
            schedule_id=job.id,
            workflow_name=job.name.replace("schedule:", ""),
            cron=str(job.trigger),
            next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
            enabled=True,
        ))
    return items


# ---- Internal helpers ----

def _load_or_404(workflow_id: str, workflow_path: str) -> Any:
    state = load_workflow_state(workflow_id, workflow_path)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return state


def _handle_bus_workflow_requested(msg: Dict[str, Any]) -> None:
    payload = msg.get("payload", msg)
    name = payload.get("workflow_name")
    if not name:
        logger.warning("WorkflowRequested missing workflow_name: %s", payload)
        return
    path = resolve_workflow_path(name, _search_paths())
    if path is None:
        logger.error("WorkflowRequested for unknown workflow: %s", name)
        return
    try:
        workflow = load_workflow(str(path))
        state = create_workflow_state(workflow.name, str(path), workflow.steps, payload.get("initial_context"))
        _execute_and_publish(workflow, str(path), state, payload.get("initial_context"), payload.get("role_override"), _bus())
    except Exception:
        logger.exception("Failed to run scheduled workflow %s", name)


def _handle_bus_workflow_control(msg: Dict[str, Any]) -> None:
    payload = msg.get("payload", msg)
    workflow_id = payload.get("workflow_id")
    action = payload.get("action")
    if not workflow_id or not action:
        return
    state = load_workflow_state(workflow_id, "")
    if state is None:
        return
    if action == "pause":
        state = pause_workflow(state)
        _bus().publish_workflow_paused(workflow_id, {"workflow_id": workflow_id, "paused_step_index": state.current_step_index})
    elif action == "resume":
        state = resume_workflow(state)
        _bus().publish_workflow_resumed(workflow_id, {"workflow_id": workflow_id, "resuming_step_index": state.current_step_index})
    elif action == "stop":
        state = stop_workflow(state)
        _bus().publish_workflow_stopped(workflow_id, {"workflow_id": workflow_id, "completed_steps": state.current_step_index})


def _execute_and_publish(
    workflow: WorkflowDefinition,
    workflow_path: str,
    state: Any,
    initial_context: Optional[Dict[str, Any]],
    role_override: Optional[str],
    bus: EventBus,
) -> Dict[str, Any]:
    from executor import execute_workflow
    from db import insert_event, record_step_result, append_log

    try:
        result = execute_workflow(workflow, workflow_path, initial_context, role_override, initial_state=state)
    except Exception as exc:
        state = fail_workflow(state, str(exc))
        bus.publish_workflow_failed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "error": str(exc),
            "completed_steps": state.current_step_index,
        })
        return {
            "workflow_id": state.workflow_id,
            "workflow_name": workflow.name,
            "status": state.status,
            "error": str(exc),
            "step_results": state.step_results,
            "context": state.context,
        }

    for idx, step_res in enumerate(state.step_results):
        record_step_result(state, step_res, idx)

    summary = {
        "workflow_id": state.workflow_id,
        "workflow_name": workflow.name,
        "status": state.status,
        "step_results": state.step_results,
        "context": state.context,
        "error": state.error,
        "total_steps": len(workflow.steps),
        "completed_steps": state.current_step_index,
    }

    if summary["status"] == "completed":
        bus.publish_workflow_completed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "final_context": summary.get("context"),
            "total_duration_seconds": None,
        })
    elif summary["status"] == "failed":
        bus.publish_workflow_failed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "error": summary.get("error"),
            "completed_steps": state.current_step_index,
        })

    return summary
