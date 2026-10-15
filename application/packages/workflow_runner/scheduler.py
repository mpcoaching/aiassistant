"""
APScheduler integration for the Workflow Engine.

Schedules are persisted in Postgres via SQLAlchemyJobStore.  When a
schedule fires, a `WorkflowRequested` event is published to RabbitMQ with
`trigger=scheduled`.  The engine's bus consumer picks it up like any
other workflow request.

The scheduler stores minimal metadata in the `schedules` table so it can
be queried and managed through the REST API.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.events import JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from configuration.contracts.v1.database import DatabaseConfiguration

logger = logging.getLogger("workflow-engine.scheduler")

Scheduler = BackgroundScheduler


def _build_scheduler(database: DatabaseConfiguration) -> BackgroundScheduler:
    db_url = database.url
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if db_url.startswith("postgres+psycopg2://"):
        db_url = db_url.replace("postgres+psycopg2://", "postgresql://", 1)

    jobstores = {
        "default": SQLAlchemyJobStore(url=db_url),
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=5),
    }
    job_defaults = {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    }
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )
    return scheduler


def schedule_workflow(
    scheduler: BackgroundScheduler,
    schedule_id: str,
    workflow_name: str,
    cron: str,
    initial_context: dict[str, Any] | None = None,
    role_override: str | None = None,
    publish_callback: Any | None = None,
) -> str:
    initial_context = initial_context or {}
    existing = scheduler.get_job(schedule_id)
    if existing:
        scheduler.remove_job(schedule_id)

    def _fire(_event: JobExecutionEvent | None = None) -> None:
        payload = {
            "event_id": str(__import__("uuid").uuid4()),
            "workflow_name": workflow_name,
            "initial_context": initial_context,
            "role_override": role_override,
            "trigger": "scheduled",
            "schedule_id": schedule_id,
            "correlation_id": schedule_id,
        }
        if publish_callback is not None:
            try:
                publish_callback("WorkflowRequested", schedule_id, payload)
            except Exception:
                logger.exception("Failed to publish scheduled WorkflowRequested for %s", schedule_id)

    trigger = CronTrigger.from_crontab(cron)
    scheduler.add_job(
        func=_fire,
        trigger=trigger,
        id=schedule_id,
        name=f"schedule:{workflow_name}",
        kwargs={"_event": None},
        replace_existing=True,
    )
    logger.info("Scheduled workflow %s with cron %s (id=%s)", workflow_name, cron, schedule_id)
    return schedule_id


def start_scheduler(scheduler: BackgroundScheduler) -> None:
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")


def shutdown_scheduler(scheduler: BackgroundScheduler) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")


def get_scheduled_jobs(scheduler: BackgroundScheduler) -> list:
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs
