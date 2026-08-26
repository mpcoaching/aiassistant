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
  GET  /capabilities                 — list enterprise capabilities with availability
  GET  /capabilities/{capability_id}/availability — query enterprise capability availability
  GET  /roles                        — list enterprise-plane roles
  GET  /work                         — list enterprise-plane work items
  GET  /work/{work_id}               — inspect a work item
  POST /work/{work_id}/process       — execute a specific work item
  POST /worker/run                   — worker picks up and executes its assigned work
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
from concepts import ConceptStore

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
from organisation.src.worker import Worker
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

_concept_store = ConceptStore()

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
    execution_outputs: dict[str, Any] | None = None
    execution_artifacts: list[str] = Field(default_factory=list)



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

from composition import create_assistant
from capability_selection_telemetry import CapabilitySelectionTelemetry

_telemetry_persistence_path = os.environ.get("CAPABILITY_TELEMETRY_PATH", "data/capability_selection_telemetry.jsonl")
_capability_selection_telemetry = CapabilitySelectionTelemetry(persistence_path=_telemetry_persistence_path)
_capability_registry = None
_capability_discovery = None

_assistant = create_assistant(capability_selection_telemetry=_capability_selection_telemetry)

_org_plane = None
_work_management = None
_enterprise_capability_query = None

try:
    from organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter
    from role import Role
    _org_plane = InMemoryOrganisationControlPlane()
    _org_plane.register_role(Role(id="researcher", name="Researcher", authority_ids=[]))
    _work_management = WorkManagementAdapter(_org_plane)
    from organisation.src.adapters.enterprise_capability_query_adapter import (
        EnterpriseCapabilityQueryAdapter,
    )
    _enterprise_capability_query = EnterpriseCapabilityQueryAdapter(_org_plane)
except Exception:
    _org_plane = None
    _work_management = None
    _enterprise_capability_query = None

try:
    from capability import Capability, CapabilityKind
    from capability_registry.src.capabilities import CapabilityRegistry
    from capability_registry.src.concept_store_adapter import (
        ConceptStoreCapabilityRepository,
    )
    from concepts import ConceptStore

    _capability_store = ConceptStore()
    _capability_repository = ConceptStoreCapabilityRepository(_capability_store)
    _capability_registry = CapabilityRegistry(_capability_repository)

    _real_capability = Capability(
        id="real-capability",
        name="Real Capability",
        description="A real executable capability for Increment 21T proof",
        owner="core",
        created_by="api-setup",
        capability_kind=CapabilityKind.SKILL,
        tags=["skill"],
    )
    _capability_registry.register(_real_capability)
except Exception:
    _capability_registry = None

try:
    from capability_matcher import RelevanceMatcher
    from capability_registry.src.adapters.capability_discovery_adapter import (
        CapabilityDiscoveryAdapter,
    )
    if _capability_registry is not None:
        _matcher = RelevanceMatcher()
        _capability_discovery = CapabilityDiscoveryAdapter(
            registry=_capability_registry,
            matcher=_matcher,
        )
except Exception:
    _capability_discovery = None

try:
    from capability_deployment import (
        CapabilityDeployment,
        CompiledRef,
        ExecutionMode,
        Transport,
    )
    from deployment_resolver import DeploymentResolver
    from workflow_runner.src.adapters.capability_execution_adapter import (
        CapabilityExecutionAdapter,
    )

    _capability_deployment = CapabilityDeployment(
        capability_id="real-capability",
        environment="default",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=CompiledRef(
            module_path="tests.real_capability",
            entrypoint="run",
        ),
    )
    _capability_resolver = DeploymentResolver([_capability_deployment])

    def _capability_deployment_factory(capability: Capability) -> CapabilityDeployment | None:
        try:
            return _capability_resolver.resolve(capability.id, "default")
        except Exception:
            return None

    if _capability_registry is not None:
        _capability_execution = CapabilityExecutionAdapter(
            registry=_capability_registry,
            deployment_factory=_capability_deployment_factory,
        )
except Exception:
    _capability_execution = None

_assistant = create_assistant(
    capability_selection_telemetry=_capability_selection_telemetry,
    capability_discovery=_capability_discovery,
    work_management=_work_management,
    enterprise_capability_query=_enterprise_capability_query,
)


@app.post("/assistant/chat", response_model=_ChatResponse)
async def assistant_chat(body: _ChatRequest) -> _ChatResponse:
    from chat import ChatRequest

    request = ChatRequest(
        message=body.message,
        session_id=body.session_id,
        user_id=body.user_id,
        context=body.context,
    )
    response = _assistant.chat(request)
    return _ChatResponse(
        message=response.message,
        session_id=response.session_id,
        status=response.status,
        reasoning=response.reasoning,
        previous_solution=response.previous_solution,
        human_input_request=response.human_input_request,
        capability_candidates=response.capability_candidates,
        telemetry=response.telemetry,
        execution_outputs=response.execution_outputs,
        execution_artifacts=response.execution_artifacts,
    )


@app.post("/assistant/chat/{session_id}/resume")
async def assistant_chat_resume(session_id: str, body: dict[str, Any]) -> _ChatResponse:
    response = _assistant.resume_with_human_input(session_id, body)
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

    _concept_store.upsert(concept)

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
    context = (body or {}).get("context", {})
    result = _assistant.execute_selected_capability(capability_id=capability_id, context=context)
    return _ExecutionResultResponse(
        outputs=result.outputs,
        artifacts=result.artifacts,
        telemetry=result.telemetry,
    )


class _CapabilityFeedbackRequest(BaseModel):
    match_event_id: str
    action: str
    selected_capability_id: str | None = None


class _CapabilityFeedbackResponse(BaseModel):
    match_event_id: str
    action: str
    status: str = "recorded"


@app.post("/assistant/capability/feedback", response_model=_CapabilityFeedbackResponse)
async def assistant_capability_feedback(body: _CapabilityFeedbackRequest) -> _CapabilityFeedbackResponse:
    _assistant.record_capability_feedback(
        match_event_id=body.match_event_id,
        user_action=body.action,
        selected_capability_id=body.selected_capability_id,
    )
    return _CapabilityFeedbackResponse(
        match_event_id=body.match_event_id,
        action=body.action,
    )


class _TelemetryEventResponse(BaseModel):
    event_id: str
    timestamp: str
    request_text: str
    session_id: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    candidate_scores: list[float] = Field(default_factory=list)
    top_score: float = 0.0
    score_gap: float = 0.0
    candidate_count: int = 0
    interaction_type: str = "select"
    user_action: str | None = None
    selected_capability_id: str | None = None


class _TelemetryStatsResponse(BaseModel):
    total_events: int
    total_sessions: int
    reformulation_candidates: int
    outcomes: dict[str, int] = Field(default_factory=dict)
    gap_distribution: dict[str, int] = Field(default_factory=dict)
    score_distribution: dict[str, int] = Field(default_factory=dict)
    count_distribution: dict[str, int] = Field(default_factory=dict)


@app.get("/assistant/telemetry/events", response_model=list[_TelemetryEventResponse])
async def assistant_telemetry_events() -> list[_TelemetryEventResponse]:
    events = _capability_selection_telemetry.get_events()
    return [
        _TelemetryEventResponse(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            request_text=event.request_text,
            session_id=event.session_id,
            candidate_ids=event.candidate_ids,
            candidate_scores=event.candidate_scores,
            top_score=event.top_score,
            score_gap=event.score_gap,
            candidate_count=event.candidate_count,
            interaction_type=event.interaction_type,
            user_action=event.user_action,
            selected_capability_id=event.selected_capability_id,
        )
        for event in events
    ]


@app.get("/assistant/telemetry/sessions/{session_id}", response_model=list[_TelemetryEventResponse])
async def assistant_telemetry_session(session_id: str) -> list[_TelemetryEventResponse]:
    events = _capability_selection_telemetry.get_events_by_session(session_id)
    return [
        _TelemetryEventResponse(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            request_text=event.request_text,
            session_id=event.session_id,
            candidate_ids=event.candidate_ids,
            candidate_scores=event.candidate_scores,
            top_score=event.top_score,
            score_gap=event.score_gap,
            candidate_count=event.candidate_count,
            interaction_type=event.interaction_type,
            user_action=event.user_action,
            selected_capability_id=event.selected_capability_id,
        )
        for event in events
    ]


@app.get("/assistant/telemetry/reformulations", response_model=list[_TelemetryEventResponse])
async def assistant_telemetry_reformulations() -> list[_TelemetryEventResponse]:
    events = _capability_selection_telemetry.get_reformulation_candidates()
    return [
        _TelemetryEventResponse(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            request_text=event.request_text,
            session_id=event.session_id,
            candidate_ids=event.candidate_ids,
            candidate_scores=event.candidate_scores,
            top_score=event.top_score,
            score_gap=event.score_gap,
            candidate_count=event.candidate_count,
            interaction_type=event.interaction_type,
            user_action=event.user_action,
            selected_capability_id=event.selected_capability_id,
        )
        for event in events
    ]


@app.post("/assistant/telemetry/export")
async def assistant_telemetry_export(body: dict[str, Any]) -> dict[str, str]:
    output_path = body.get("output_path", "data/telemetry_export.json")
    _capability_selection_telemetry.export_to_json(output_path)
    return {"status": "exported", "path": output_path}


@app.get("/assistant/telemetry/stats", response_model=_TelemetryStatsResponse)
async def assistant_telemetry_stats() -> _TelemetryStatsResponse:
    events = _capability_selection_telemetry.get_events()
    sessions = _capability_selection_telemetry.get_reformulation_candidates()

    outcomes: dict[str, int] = {}
    gap_distribution: dict[str, int] = {}
    score_distribution: dict[str, int] = {}
    count_distribution: dict[str, int] = {}

    for event in events:
        if event.user_action:
            outcomes[event.user_action] = outcomes.get(event.user_action, 0) + 1

        if event.score_gap == 0.0:
            bucket = "gap=0.0"
        elif event.score_gap <= 0.1:
            bucket = "0<gap<=0.1"
        elif event.score_gap <= 0.2:
            bucket = "0.1<gap<=0.2"
        elif event.score_gap <= 0.5:
            bucket = "0.2<gap<=0.5"
        else:
            bucket = "gap>0.5"
        gap_distribution[bucket] = gap_distribution.get(bucket, 0) + 1

        if event.top_score <= 0.5:
            bucket = "0<score<=0.5"
        elif event.top_score <= 0.75:
            bucket = "0.5<score<=0.75"
        else:
            bucket = "score>0.75"
        score_distribution[bucket] = score_distribution.get(bucket, 0) + 1

        if event.candidate_count <= 2:
            bucket = "count<=2"
        elif event.candidate_count == 3:
            bucket = "count=3"
        elif event.candidate_count == 4:
            bucket = "count=4"
        else:
            bucket = "count>=5"
        count_distribution[bucket] = count_distribution.get(bucket, 0) + 1

    total_sessions = len(set(event.session_id for event in events if event.session_id))

    return _TelemetryStatsResponse(
        total_events=len(events),
        total_sessions=total_sessions,
        reformulation_candidates=len(sessions),
        outcomes=outcomes,
        gap_distribution=gap_distribution,
        score_distribution=score_distribution,
        count_distribution=count_distribution,
    )


class _RoleResponse(BaseModel):
    role_id: str
    name: str
    status: str
    authority_ids: list[str] = []


class _WorkResponse(BaseModel):
    work_id: str
    title: str
    description: str
    status: str
    priority: str
    work_type: str
    accountable_role_id: str
    assignee_role_id: str | None = None
    assignee_person_id: str | None = None
    assignee_agent_id: str | None = None
    required_capability_ids: list[str] = []
    outcome: dict[str, Any] | None = None
    output_path: str | None = None


class _CapabilityResponse(BaseModel):
    capability_id: str
    name: str
    description: str
    kind: str
    available: bool
    eta_seconds: int | None = None
    assignee: str | None = None
    reason: str = ""


class _CapabilityAvailabilityResponse(BaseModel):
    capability_id: str
    available: bool
    eta_seconds: int | None = None
    assignee: str | None = None
    reason: str = ""


@app.get("/capabilities", response_model=list[_CapabilityResponse])
async def list_capabilities() -> list[_CapabilityResponse]:
    if _capability_registry is None:
        raise HTTPException(status_code=501, detail="Capability registry not configured")
    capabilities = []
    for cap in _capability_registry.list_all():
        availability = _org_plane.query_capability(cap.id) if _org_plane else None
        capabilities.append(_CapabilityResponse(
            capability_id=cap.id,
            name=cap.name,
            description=cap.description or "",
            kind=cap.capability_kind.value if cap.capability_kind else "unknown",
            available=availability["available"] if availability else False,
            eta_seconds=availability.get("eta_seconds") if availability else None,
            assignee=availability.get("assignee") if availability else None,
            reason=availability.get("reason", "") if availability else "",
        ))
    return capabilities


@app.get("/capabilities/{capability_id}/availability", response_model=_CapabilityAvailabilityResponse)
async def query_capability_availability(capability_id: str) -> _CapabilityAvailabilityResponse:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    result = _org_plane.query_capability(capability_id)
    if result is None:
        return _CapabilityAvailabilityResponse(
            capability_id=capability_id,
            available=False,
            reason="Capability not found in enterprise plane",
        )
    return _CapabilityAvailabilityResponse(
        capability_id=result["capability_id"],
        available=result["available"],
        eta_seconds=result.get("eta_seconds"),
        assignee=result.get("assignee"),
        reason=result.get("reason", ""),
    )


@app.get("/roles", response_model=list[_RoleResponse])
async def list_roles() -> list[_RoleResponse]:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    roles = _org_plane.list_roles()
    return [
        _RoleResponse(
            role_id=role.id,
            name=role.name,
            status=role.status.value,
            authority_ids=list(role.authority_ids),
        )
        for role in roles
    ]


@app.get("/work", response_model=list[_WorkResponse])
async def list_work() -> list[_WorkResponse]:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    work_items = []
    for work in _org_plane.list_work():
        work_items.append(_WorkResponse(
            work_id=work.id,
            title=work.title,
            description=work.description,
            status=work.status.value,
            priority=work.priority,
            work_type=work.work_type,
            accountable_role_id=work.accountable_role_id,
            assignee_role_id=work.assignee_role_id,
            assignee_person_id=work.assignee_person_id,
            assignee_agent_id=work.assignee_agent_id,
            required_capability_ids=list(work.required_capability_ids),
            outcome=work.outcome,
            output_path=work.outcome.get("output_path") if work.outcome else None,
        ))
    return work_items


@app.get("/work/{work_id}", response_model=_WorkResponse)
async def get_work(work_id: str) -> _WorkResponse:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    work = _org_plane.get_work(work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return _WorkResponse(
        work_id=work.id,
        title=work.title,
        description=work.description,
        status=work.status.value,
        priority=work.priority,
        work_type=work.work_type,
        accountable_role_id=work.accountable_role_id,
        assignee_role_id=work.assignee_role_id,
        assignee_person_id=work.assignee_person_id,
        assignee_agent_id=work.assignee_agent_id,
        required_capability_ids=list(work.required_capability_ids),
        outcome=work.outcome,
        output_path=work.outcome.get("output_path") if work.outcome else None,
    )


@app.post("/work/{work_id}/process")
async def process_work(work_id: str) -> dict[str, Any]:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    work = _org_plane.get_work(work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    worker = Worker(
        capability_execution=_capability_execution,
        capability_registry=_capability_registry,
    )
    result = worker.execute(work, _org_plane)
    return {"work_id": work_id, "status": result.get("status", "completed"), "outcome": result}


@app.post("/worker/run")
async def run_worker() -> dict[str, Any]:
    if _org_plane is None:
        raise HTTPException(status_code=501, detail="Organisation plane not configured")
    worker = Worker(
        capability_execution=_capability_execution,
        capability_registry=_capability_registry,
    )
    work = worker.pickup(_org_plane)
    if work is None:
        raise HTTPException(status_code=404, detail="No work available for worker")
    result = worker.execute(work, _org_plane)
    return {"work_id": work.id, "status": result.get("status", "completed"), "outcome": result}


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
