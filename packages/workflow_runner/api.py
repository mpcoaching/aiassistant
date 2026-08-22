"""
FastAPI REST API for the Workflow Engine.

Endpoints:
  GET  /health                      — liveness probe
  GET  /workflows                   — list workflow definitions
  POST /workflows                   — create a workflow definition (write YAML)
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from configuration import (
    ConfigurationManager,
    DatabaseConfiguration,
    DotEnvProvider,
    LangGraphRuntimeConfiguration,
    MessageBusConfiguration,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Allow imports from the workflow_runner package directory when run as a package
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from capability_registry.src.capabilities import ConceptKind
from capability_registry.src.capability_request import CapabilityRequest
from capability_registry.src.concepts import (
    EnterpriseConcept,
    Provenance,
    RecognitionLevel,
)

from bus import EventBus
from db import (
    create_workflow_state,
    fail_workflow,
    load_workflow_state,
    pause_workflow,
    resume_workflow,
    stop_workflow,
)
from db import (
    delete_schedule as _db_delete_schedule,
)
from loader import load_workflow, resolve_workflow_path
from models import Step, WorkflowDefinition
from runtime_client import configure as _configure_runtime_client
from scheduler import (
    _build_scheduler,
    schedule_workflow,
    shutdown_scheduler,
    start_scheduler,
)

logger = logging.getLogger("workflow-engine.api")
app = FastAPI(title="Workflow Engine", version="1.0.0")

_bus_cfg: MessageBusConfiguration | None = None
_db_cfg: DatabaseConfiguration | None = None
_langgraph_cfg: LangGraphRuntimeConfiguration | None = None

# Resolve repo root for workflow discovery (walk up to .git or .kilo)
_script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = _script_dir
for _parent in [_script_dir] + list(_script_dir.parents):
    if (_parent / ".git").exists() or (_parent / ".kilo").exists():
        _REPO_ROOT = _parent
        break
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
        if _bus_cfg is None:
            raise RuntimeError("MessageBusConfiguration not resolved")
        app.state.bus = EventBus(url=_bus_cfg.url, fallback_dir=_bus_cfg.fallback_dir)
        try:
            app.state.bus.declare_topology()
        except Exception:
            logger.exception("Failed to declare bus topology")
    return app.state.bus


def _scheduler() -> _SchedulerHolder:
    if not hasattr(app.state, "scheduler"):
        if _db_cfg is None:
            raise RuntimeError("DatabaseConfiguration not resolved")
        sched = _build_scheduler(database=_db_cfg)
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
    description: str | None = None
    path: str


class RunRequest(BaseModel):
    initial_context: dict[str, Any] | None = None
    role_override: str | None = None


class ScheduleRequest(BaseModel):
    workflow_name: str = Field(..., description="Name of the workflow to schedule")
    schedule_id: str = Field(..., description="Unique id for the schedule")
    cron: str = Field(..., description="Cron expression (e.g. '0 8 * * *')")
    initial_context: dict[str, Any] | None = None
    role_override: str | None = None


class StepInput(BaseModel):
    type: str = Field(..., description="Step type: skill | tool | workflow")
    name: str
    uses: str = Field(..., description="Reference to the skill, tool, or sub-workflow")
    with_: dict[str, Any] | None = Field(None, alias="with", description="Input parameters for the step")


class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., description="Unique workflow name, e.g. 'my.team.workflow'")
    description: str | None = None
    role: list[str] | None = None
    steps: list[StepInput]


class ScheduleResponse(BaseModel):
    schedule_id: str
    workflow_name: str
    cron: str
    next_run_time: str | None = None
    enabled: bool


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    current_step_index: int
    total_steps: int
    error: str | None = None
    step_results: list[dict[str, Any] | None] = Field(default_factory=list)


# ---- Lifecycle ----

@app.on_event("startup")
async def on_startup() -> None:
    global _bus_cfg, _db_cfg, _langgraph_cfg
    logger.info("Workflow Engine API starting up")
    try:
        manager = ConfigurationManager(DotEnvProvider())
        _bus_cfg = manager.resolve(MessageBusConfiguration)
        _db_cfg = manager.resolve(DatabaseConfiguration)
        _langgraph_cfg = manager.resolve(LangGraphRuntimeConfiguration)
        _configure_runtime_client(_langgraph_cfg)

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
        logger.exception("Error during scheduler shutdown")
    try:
        _bus().shutdown()
    except Exception:
        logger.exception("Error during bus shutdown")


# ---- Routes ----

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/workflows", response_model=list[WorkflowListItem])
async def list_workflows() -> list[WorkflowListItem]:
    items: list[WorkflowListItem] = []
    for base in _WORKFLOW_PATHS:
        if not base.exists():
            continue
        for f in sorted(base.glob("*.yaml")):
            name = f.stem
            desc: str | None = None
            try:
                wf = load_workflow(str(f))
                desc = wf.description
                name = wf.name
            except Exception:
                logger.debug("Failed to load workflow %s", f, exc_info=True)
            items.append(WorkflowListItem(name=name, description=desc, path=str(f)))
    return items


@app.post("/workflows", response_model=WorkflowListItem, status_code=201)
async def create_workflow(body: CreateWorkflowRequest) -> WorkflowListItem:
    if not body.name or "/" in body.name or "\\" in body.name or ".." in body.name:
        raise HTTPException(status_code=400, detail="Invalid workflow name (no path separators)")
    try:
        steps = [Step(type=s.type, name=s.name, uses=s.uses, with_=s.with_) for s in body.steps]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid step: {exc}") from exc

    workflow = WorkflowDefinition(
        name=body.name,
        description=body.description,
        role=body.role,
        steps=steps,
    )
    target = _REPO_ROOT / "agentic" / "docs" / "workflows" / f"{body.name}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:  # noqa: ASYNC230
        yaml.safe_dump(workflow.model_dump(mode="json", by_alias=True, exclude_none=True), f, sort_keys=False)

    wf = load_workflow(str(target))
    return WorkflowListItem(name=wf.name, description=wf.description, path=str(target))


@app.post("/workflows/{name}/run")
async def run_workflow(name: str, body: RunRequest | None = None) -> dict[str, Any]:
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
        database_url=_db_cfg.url if _db_cfg else None,
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
        state = load_workflow_state(workflow_id, workflow_path, database_url=_db_cfg.url if _db_cfg else None)
    else:
        state = None
        for p in _WORKFLOW_PATHS:
            state = load_workflow_state(workflow_id, str(p), database_url=_db_cfg.url if _db_cfg else None)
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
async def pause_workflow_endpoint(workflow_id: str, workflow_path: str) -> dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot pause workflow in status {state.status}")
    state = pause_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
    _bus().publish_workflow_paused(workflow_id, {
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "paused_step_index": state.current_step_index,
        "reason": "user_requested",
    })
    return {"status": "paused", "workflow_id": workflow_id}


@app.post("/workflows/{workflow_id}/resume")
async def resume_workflow_endpoint(workflow_id: str, workflow_path: str) -> dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume workflow in status {state.status}")
    state = resume_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
    _bus().publish_workflow_resumed(workflow_id, {
        "event_id": str(__import__("uuid").uuid4()),
        "workflow_id": workflow_id,
        "resuming_step_index": state.current_step_index,
    })
    return {"status": "running", "workflow_id": workflow_id}


@app.post("/workflows/{workflow_id}/stop")
async def stop_workflow_endpoint(workflow_id: str, workflow_path: str) -> dict[str, Any]:
    state = _load_or_404(workflow_id, workflow_path)
    if state.status not in ("running", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot stop workflow in status {state.status}")
    state = stop_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
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
async def delete_schedule(schedule_id: str) -> dict[str, Any]:
    holder = _scheduler()
    try:
        holder.sched.remove_job(schedule_id)
    except Exception:
        logger.debug("Job %s not found in scheduler", schedule_id, exc_info=True)
    _bus().publish_schedule_removed(schedule_id, {
        "schedule_id": schedule_id,
    })
    try:
        _db_delete_schedule(schedule_id, database_url=_db_cfg.url if _db_cfg else None)
    except Exception:
        logger.debug("Failed to delete schedule %s from database", schedule_id, exc_info=True)
    return {"status": "removed", "schedule_id": schedule_id}


@app.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules() -> list[ScheduleResponse]:
    holder = _scheduler()
    items: list[ScheduleResponse] = []
    for job in holder.sched.get_jobs():
        items.append(ScheduleResponse(
            schedule_id=job.id,
            workflow_name=job.name.replace("schedule:", ""),
            cron=str(job.trigger),
            next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
            enabled=True,
        ))
    return items


# ---- Business Service endpoints (C7) --------------------------------------

class _SessionRecord(BaseModel):
    session_id: str
    user_id: str | None = None
    objectives: str = ""
    outcomes: str | None = None
    learnings: str | None = None
    status: str = "open"


class _TaskRecord(BaseModel):
    task_id: str
    user_id: str | None = None
    description: str
    status: str = "TODO"
    priority: str = "medium"
    due_date: str | None = None
    work_session_id: str | None = None


class _LeadProfile(BaseModel):
    lead_id: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    enriched_data: dict[str, Any] = Field(default_factory=dict)
    suggestions: dict[str, Any] = Field(default_factory=dict)


_SESSIONS: dict[str, _SessionRecord] = {}
_TASKS: dict[str, _TaskRecord] = {}
_LEADS: dict[str, _LeadProfile] = {}


@app.post("/sessions", response_model=_SessionRecord)
async def create_session(body: dict[str, Any]) -> _SessionRecord:
    sid = str(__import__("uuid").uuid4())[:8]
    record = _SessionRecord(session_id=sid, **body)
    _SESSIONS[sid] = record
    _bus().publish_workflow_started(sid, {"event_id": str(__import__("uuid").uuid4()), "workflow_id": sid, "type": "work_session_created"})
    return record


@app.put("/sessions/{session_id}/close")
async def close_session(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    record = _SESSIONS.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    record.outcomes = body.get("outcomes")
    record.learnings = body.get("learnings")
    record.status = "closed"
    return {"status": "closed", "session_id": session_id}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> _SessionRecord:
    record = _SESSIONS.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@app.get("/sessions")
async def list_sessions() -> list[_SessionRecord]:
    return list(_SESSIONS.values())


@app.post("/tasks", response_model=_TaskRecord)
async def create_task(body: dict[str, Any]) -> _TaskRecord:
    tid = str(__import__("uuid").uuid4())[:8]
    record = _TaskRecord(task_id=tid, **body)
    _TASKS[tid] = record
    return record


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> _TaskRecord:
    record = _TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return record


@app.put("/tasks/{task_id}")
async def update_task(task_id: str, body: dict[str, Any]) -> _TaskRecord:
    record = _TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in body.items():
        setattr(record, k, v)
    return record


@app.patch("/tasks/{task_id}/status")
async def patch_task_status(task_id: str, body: dict[str, Any]) -> _TaskRecord:
    record = _TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    record.status = body.get("status", record.status)
    return record


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict[str, str]:
    _TASKS.pop(task_id, None)
    return {"status": "removed", "task_id": task_id}


@app.get("/tasks")
async def list_tasks() -> list[_TaskRecord]:
    return list(_TASKS.values())


@app.post("/leads/enrich")
async def enrich_lead(body: dict[str, Any]) -> dict[str, str]:
    lid = str(__import__("uuid").uuid4())[:8]
    _LEADS[lid] = _LeadProfile(lead_id=lid, raw_data=body)
    _bus().publish_workflow_started(lid, {"event_id": str(__import__("uuid").uuid4()), "workflow_id": lid, "type": "lead_enriched"})
    return {"lead_id": lid}


@app.get("/leads/{lead_id}")
async def get_lead(lead_id: str) -> _LeadProfile:
    profile = _LEADS.get(lead_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return profile


@app.get("/leads")
async def list_leads() -> list[_LeadProfile]:
    return list(_LEADS.values())


# ---- Assistant Chat (Phase 6) ----------------------------------------------

class _ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class _ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: str | None = None
    previous_solution: dict[str, Any] | None = None
    human_input_request: dict[str, Any] | None = None
    capability_candidates: list[dict[str, Any]] | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)



class _CapabilityRequestApprovalRequest(BaseModel):
    request_id: str
    action: str = Field(..., description="approve | reject | modify")
    capability_request: dict[str, Any] | None = None
    modified_spec: dict[str, Any] | None = None


class _CapabilityRequestApprovalResponse(BaseModel):
    request_id: str
    action: str
    status: str
    concept_id: str | None = None
    message: str
    governance: dict[str, Any] | None = None


class _ExecutionResultResponse(BaseModel):
    outputs: dict[str, Any]
    artifacts: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)

_chat_service: Any | None = None


def _get_chat_service() -> Any:
    global _chat_service
    if _chat_service is None:
        _script_dir = Path(__file__).resolve().parent
        _packages_root = _script_dir.parent.parent
        for _pkg in ["ai", "bus", "langgraph", "capability_registry"]:
            _src = _packages_root / _pkg / "src"
            if _src.exists() and str(_src) not in sys.path:
                sys.path.insert(0, str(_src))
        from chat import AssistantChatService
        from langgraph_runtime import LangGraphRuntime
        _chat_service = AssistantChatService(runtime=LangGraphRuntime())
    return _chat_service


@app.post("/assistant/chat", response_model=_ChatResponse)
async def assistant_chat(body: _ChatRequest) -> _ChatResponse:
    service = _get_chat_service()
    from chat import ChatRequest
    request = ChatRequest(
        message=body.message,
        session_id=body.session_id,
        user_id=body.user_id,
        context=body.context,
    )
    response = service.chat(request)
    return _ChatResponse(
        message=response.message,
        session_id=response.session_id,
        status=response.status,
        reasoning=response.reasoning,
        previous_solution=response.previous_solution,
        human_input_request=response.human_input_request,
        capability_candidates=response.capability_candidates,
        telemetry=response.telemetry,
    )


@app.post("/assistant/chat/{session_id}/resume")
async def assistant_chat_resume(session_id: str, body: dict[str, Any]) -> _ChatResponse:
    service = _get_chat_service()
    response = service.resume_with_human_input(session_id, body)
    return _ChatResponse(
        message=response.message,
        session_id=response.session_id,
        status=response.status,
        telemetry=response.telemetry,
    )




def _validate_capability_request(payload: dict[str, Any]) -> CapabilityRequest:
    """Validate raw dict against CapabilityRequest model."""
    try:
        return CapabilityRequest.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CapabilityRequest: {exc}",
        ) from exc


def _approve_capability_request(
    request: CapabilityRequest,
    approver: str = "system",
    rationale: str | None = None,
) -> EnterpriseConcept:
    """Persist an approved CapabilityRequest as a draft EnterpriseConcept."""
    concept = EnterpriseConcept(
        id=f"cap-{request.name.lower().replace(' ', '-')}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        kind=ConceptKind.CAPABILITY,
        name=request.name,
        description=request.purpose,
        owner=request.requester,
        created_by=approver,
        status="draft",
        tags=["capability-request", "draft"],
        provenance=Provenance(
            source_session_id=request.request_id,
            recognition_level=RecognitionLevel.SYNTHESIS,
        ),
        payload={
            "capability_request": request.model_dump(mode="json"),
            "governance": {
                "action": "approved",
                "approved_by": approver,
                "approved_at": datetime.now(UTC).isoformat(),
                "rationale": rationale or "",
            },
        },
    )
    return concept


@app.post("/assistant/capability-request/{request_id}/approve", response_model=_CapabilityRequestApprovalResponse)
async def assistant_capability_request_approve(
    request_id: str,
    body: _CapabilityRequestApprovalRequest,
) -> _CapabilityRequestApprovalResponse:
    if body.request_id != request_id:
        raise HTTPException(status_code=400, detail="request_id mismatch")

    action = body.action.lower()
    if action not in ("approve", "reject", "modify"):
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    if not body.capability_request:
        raise HTTPException(status_code=400, detail="capability_request is required")

    request = _validate_capability_request(body.capability_request)

    if action == "modify":
        if not body.modified_spec:
            raise HTTPException(status_code=400, detail="modified_spec required for modify action")
        modified = _validate_capability_request(body.modified_spec)
        request.name = modified.name
        request.purpose = modified.purpose
        request.inputs = modified.inputs
        request.outputs = modified.outputs
        request.acceptance_criteria = modified.acceptance_criteria
        request.governance = {
            "action": "modified",
            "modified_by": request.requester,
            "modified_at": datetime.now(UTC).isoformat(),
        }

    if action == "reject":
        return _CapabilityRequestApprovalResponse(
            request_id=request_id,
            action="rejected",
            status="rejected",
            message="Capability request rejected.",
        )

    request.approve(approver=request.requester, rationale=request.governance.get("rationale"))
    concept = _approve_capability_request(request, approver=request.requester)

    from concepts import ConceptStore
    store = ConceptStore()
    store.upsert(concept)

    return _CapabilityRequestApprovalResponse(
        request_id=request_id,
        action="approved",
        status="draft",
        concept_id=concept.id,
        message="Capability request approved. Implementation pending.",
        governance=concept.payload.get("governance"),
    )


@app.post("/assistant/capability/{capability_id}/execute", response_model=_ExecutionResultResponse)
async def assistant_capability_execute(
    capability_id: str,
    body: dict[str, Any] | None = None,
) -> _ExecutionResultResponse:
    service = _get_chat_service()
    context = (body or {}).get("context", {})
    result = service.execute_selected_capability(capability_id=capability_id, context=context)
    return _ExecutionResultResponse(
        outputs=result.outputs,
        artifacts=result.artifacts,
        telemetry=result.telemetry,
    )


# ---- Internal helpers ----

def _load_or_404(workflow_id: str, workflow_path: str) -> Any:
    state = load_workflow_state(workflow_id, workflow_path, database_url=_db_cfg.url if _db_cfg else None)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return state


def _handle_bus_workflow_requested(msg: dict[str, Any]) -> None:
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
        state = create_workflow_state(workflow.name, str(path), workflow.steps, payload.get("initial_context"), database_url=_db_cfg.url if _db_cfg else None)
        _execute_and_publish(workflow, str(path), state, payload.get("initial_context"), payload.get("role_override"), _bus())
    except Exception:
        logger.exception("Failed to run scheduled workflow %s", name)


def _handle_bus_workflow_control(msg: dict[str, Any]) -> None:
    payload = msg.get("payload", msg)
    workflow_id = payload.get("workflow_id")
    action = payload.get("action")
    if not workflow_id or not action:
        return
        state = load_workflow_state(workflow_id, "", database_url=_db_cfg.url if _db_cfg else None)
    if state is None:
        return
    if action == "pause":
        state = pause_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
        _bus().publish_workflow_paused(workflow_id, {"workflow_id": workflow_id, "paused_step_index": state.current_step_index})
    elif action == "resume":
        state = resume_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
        _bus().publish_workflow_resumed(workflow_id, {"workflow_id": workflow_id, "resuming_step_index": state.current_step_index})
    elif action == "stop":
        state = stop_workflow(state, database_url=_db_cfg.url if _db_cfg else None)
        _bus().publish_workflow_stopped(workflow_id, {"workflow_id": workflow_id, "completed_steps": state.current_step_index})


def _execute_and_publish(
    workflow: WorkflowDefinition,
    workflow_path: str,
    state: Any,
    initial_context: dict[str, Any] | None,
    role_override: str | None,
    bus: EventBus,
) -> dict[str, Any]:
    from db import record_step_result
    from models import StepResult
    from workflow_runner.executor import execute_workflow

    def _on_step_start(step: Step, index: int) -> None:
        bus.publish_step_started(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "step_index": index,
            "step_name": step.name,
            "step_type": step.type.value,
            "estimated_duration_seconds": None,
        })

    def _on_step_complete(step: Step, result: StepResult, index: int) -> None:
        bus.publish_step_completed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "step_index": index,
            "step_name": step.name,
            "status": result.status,
            "output": result.output,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
        })

    try:
        execute_workflow(
            workflow,
            workflow_path,
            initial_context,
            role_override,
            initial_state=state,
            on_step_start=_on_step_start,
            on_step_complete=_on_step_complete,
            database_url=_db_cfg.url if _db_cfg else None,
        )
    except Exception as exc:  # noqa: BLE001
        state = fail_workflow(state, str(exc), database_url=_db_cfg.url if _db_cfg else None)
        failed_step = state.steps[state.current_step_index].name if state.current_step_index < len(state.steps) else None
        bus.publish_workflow_failed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "error": str(exc),
            "failed_step": failed_step,
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
        record_step_result(state, step_res, idx, database_url=_db_cfg.url if _db_cfg else None)

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
        failed_step = state.steps[state.current_step_index].name if state.current_step_index < len(state.steps) else None
        bus.publish_workflow_failed(state.workflow_id, {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_id": state.workflow_id,
            "error": summary.get("error"),
            "failed_step": failed_step,
            "completed_steps": state.current_step_index,
        })

    return summary
