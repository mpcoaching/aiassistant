"""
RabbitMQ Bus Integration for the Workflow Engine.

Publishes workflow-mode events and consumes `WorkflowRequested` and
`WorkflowControl` messages.  Consumers are implemented as thread-safe,
idempotent handlers following `docs/SYSTEM_CONTEXT.md`.

Uses `pika` with a dedicated thread for the consumer loop so the rest of
the service (FastAPI + APScheduler) is not blocked.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import pika

logger = logging.getLogger("workflow-engine.bus")


# ---- Capability invocation envelopes (C5) ---------------------------------
# Tier 2 (in-process) and Tier 3 (bus-mediated) invocations use the SAME
# envelope; only the transport differs.

@dataclass
class CapabilityRequest:
    request_id: str
    correlation_id: str
    capability_id: str
    capability_name: str
    inputs: Dict[str, Any]
    caller_session_id: Optional[str] = None
    transport: str = "tier3_bus"
    timeout_seconds: int = 300
    context_ref: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(self.__dict__)


@dataclass
class CapabilityReply:
    request_id: str
    correlation_id: str
    status: str  # completed | approved | rejected | escalated | failed
    outputs: Dict[str, Any]
    artifacts: List[str]
    telemetry: Dict[str, Any]
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
# Directory where events are spooled when the bus is unreachable, so they
# survive outages and can be replayed on reconnect.
EVENTS_FALLBACK_DIR = os.getenv("EVENTS_FALLBACK_DIR", "/aiassistant/.events")
# Retry backoff (seconds) applied before giving up and spooling to disk.
PUBLISH_BACKOFFS = (1, 2, 4)
WORKFLOW_EXCHANGE = "workflow.mode"
CAPABILITY_EXCHANGE = "capability.mode"
KNOWLEDGE_EXCHANGE = "knowledge.mode"
DEAD_LETTER_EXCHANGE = "workflow.dead"
WORKFLOW_QUEUES = {
    "workflow.executions": ["workflow.executions"],
    "workflow.control": ["workflow.control"],
    "workflow.lifecycle": [
        "workflow.lifecycle.StepStarted",
        "workflow.lifecycle.StepCompleted",
        "workflow.lifecycle.WorkflowStarted",
        "workflow.lifecycle.WorkflowCompleted",
        "workflow.lifecycle.WorkflowFailed",
        "workflow.lifecycle.WorkflowPaused",
        "workflow.lifecycle.WorkflowResumed",
        "workflow.lifecycle.WorkflowStopped",
        "workflow.lifecycle.ScheduleCreated",
        "workflow.lifecycle.ScheduleRemoved",
    ],
}
# Capability invocation (Tier 3) and Knowledge ingestion topologies (C5).
CAPABILITY_QUEUES = {
    "capability.request": ["capability.request"],
    "capability.reply": ["capability.reply"],
}
KNOWLEDGE_QUEUES = {
    "knowledge.chunk": ["knowledge.chunk.discovered"],
}
CAPABILITY_ROUTING_KEYS = ["capability.request", "capability.reply"]
KNOWLEDGE_ROUTING_KEYS = ["knowledge.chunk.discovered"]


def _event_envelope(event_type: str, workflow_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": payload.get("event_id") or str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow_id,
        "correlation_id": payload.get("correlation_id"),
        "payload": payload,
    }


class EventBus:
    def __init__(self, url: str = RABBITMQ_URL) -> None:
        self._url = url
        self._lock = threading.Lock()
        self._consumer_thread: Optional[threading.Thread] = None
        self._consumers: list = []
        self._running = False
        self._params = pika.URLParameters(self._url)
        self._params.heartbeat = 30
        self._params.blocked_connection_timeout = 10

    def _connect(self) -> pika.BlockingConnection:
        return pika.BlockingConnection(self._params)

    def declare_topology(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                ch = conn.channel()
                for exchange in (WORKFLOW_EXCHANGE, CAPABILITY_EXCHANGE, KNOWLEDGE_EXCHANGE):
                    ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
                ch.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="topic", durable=True)

                all_queues = {
                    **WORKFLOW_QUEUES,
                    **CAPABILITY_QUEUES,
                    **KNOWLEDGE_QUEUES,
                }
                for queue_name, routing_keys in all_queues.items():
                    ch.queue_declare(queue=queue_name, durable=True, arguments={
                        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
                        "x-dead-letter-routing-key": f"dead.{queue_name}",
                    })
                    for rk in routing_keys:
                        exchange = WORKFLOW_EXCHANGE if queue_name.startswith("workflow.") else (
                            CAPABILITY_EXCHANGE if queue_name.startswith("capability.") else KNOWLEDGE_EXCHANGE
                        )
                        ch.queue_bind(exchange=exchange, queue=queue_name, routing_key=rk)

                ch.queue_declare(queue="workflow.dead", durable=True)
                ch.queue_bind(exchange=DEAD_LETTER_EXCHANGE, queue="workflow.dead", routing_key="dead.#")
                ch.close()
            finally:
                conn.close()

    # ---- capability invocation (Tier 3) ----

    def publish_capability_request(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("capability.request", "CapabilityRequest", workflow_id, payload)

    def publish_capability_reply(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("capability.reply", "CapabilityReply", workflow_id, payload)

    # ---- knowledge ingestion ----

    def publish_knowledge_chunk(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("knowledge.chunk.discovered", "KnowledgeChunkDiscovered", workflow_id, payload)

    def _write_fallback(self, routing_key: str, event_type: str, workflow_id: str, envelope: Dict[str, Any]) -> None:
        try:
            os.makedirs(EVENTS_FALLBACK_DIR, exist_ok=True)
            fname = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-{event_type}-{uuid.uuid4().hex[:8]}.json"
            path = os.path.join(EVENTS_FALLBACK_DIR, fname)
            with open(path, "w") as f:
                json.dump({
                    "routing_key": routing_key,
                    "event_type": event_type,
                    "workflow_id": workflow_id,
                    "envelope": envelope,
                }, f)
            logger.warning("Spooled undeliverable event %s to fallback file %s", event_type, path)
        except Exception:
            logger.exception("Failed to write fallback event file for %s", event_type)

    def replay_failed_events(self) -> None:
        """Re-publish events spooled to the fallback directory during outages."""
        try:
            if not os.path.isdir(EVENTS_FALLBACK_DIR):
                return
            for fname in sorted(os.listdir(EVENTS_FALLBACK_DIR)):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(EVENTS_FALLBACK_DIR, fname)
                try:
                    with open(path) as f:
                        rec = json.load(f)
                except Exception:
                    logger.exception("Failed to read fallback event %s", path)
                    continue
                try:
                    self.publish(rec["routing_key"], rec["event_type"], rec["workflow_id"], rec["envelope"]["payload"])
                    os.remove(path)
                    logger.info("Replayed fallback event %s", fname)
                except Exception:
                    logger.exception("Failed to replay fallback event %s; will retry later", path)
                    break
        except Exception:
            logger.exception("Failed to replay fallback events")

    def publish(self, routing_key: str, event_type: str, workflow_id: str, payload: Dict[str, Any]) -> None:
        envelope = _event_envelope(event_type, workflow_id, payload)
        body = json.dumps(envelope).encode("utf-8")
        max_attempts = len(PUBLISH_BACKOFFS) + 1
        with self._lock:
            for attempt in range(max_attempts):
                try:
                    conn = self._connect()
                    try:
                        ch = conn.channel()
                        ch.basic_publish(
                            exchange=WORKFLOW_EXCHANGE,
                            routing_key=routing_key,
                            body=body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                content_type="application/json",
                                message_id=envelope["event_id"],
                            ),
                        )
                        ch.close()
                        return
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass
                except pika.exceptions.AMQPConnectionError:
                    if attempt < len(PUBLISH_BACKOFFS):
                        logger.warning(
                            "Publish of %s failed (attempt %d/%d); retrying in %ss",
                            event_type, attempt + 1, max_attempts, PUBLISH_BACKOFFS[attempt],
                        )
                        time.sleep(PUBLISH_BACKOFFS[attempt])
                        continue
                    logger.exception("Failed to publish event %s after %d attempts", event_type, max_attempts)
                except Exception:
                    logger.exception("Failed to publish event %s", event_type)
                    break
            # All attempts exhausted — spool so the event survives the outage.
            self._write_fallback(routing_key, event_type, workflow_id, envelope)

    def publish_workflow_requested(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.executions", "WorkflowRequested", workflow_id, payload)

    def publish_workflow_started(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowStarted", "WorkflowStarted", workflow_id, payload)

    def publish_step_started(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.StepStarted", "StepStarted", workflow_id, payload)

    def publish_step_completed(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.StepCompleted", "StepCompleted", workflow_id, payload)

    def publish_workflow_completed(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowCompleted", "WorkflowCompleted", workflow_id, payload)

    def publish_workflow_failed(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowFailed", "WorkflowFailed", workflow_id, payload)

    def publish_workflow_paused(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowPaused", "WorkflowPaused", workflow_id, payload)

    def publish_workflow_resumed(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowResumed", "WorkflowResumed", workflow_id, payload)

    def publish_workflow_stopped(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.WorkflowStopped", "WorkflowStopped", workflow_id, payload)

    def publish_schedule_created(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.ScheduleCreated", "ScheduleCreated", workflow_id, payload)

    def publish_schedule_removed(self, workflow_id: str, payload: Dict[str, Any]) -> None:
        self.publish("workflow.lifecycle.ScheduleRemoved", "ScheduleRemoved", workflow_id, payload)

    def consume(
        self,
        queue: str,
        callback: Callable[[Dict[str, Any]], None],
        prefetch: int = 1,
    ) -> None:
        def on_message(ch, ch_method, properties, body):  # noqa: A003
            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                logger.exception("Invalid JSON in bus message")
                ch_method.basic_ack(delivery_tag=ch_method.delivery_tag)
                return
            try:
                callback(msg)
                ch_method.basic_ack(delivery_tag=ch_method.delivery_tag)
            except Exception:
                logger.exception("Bus consumer callback failed")
                ch_method.basic_nack(delivery_tag=ch_method.delivery_tag, requeue=False)

        def _run() -> None:
            conn = None
            ch = None
            try:
                conn = self._connect()
                ch = conn.channel()
                ch.basic_qos(prefetch_count=prefetch)
                ch.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=False)
                self._consumers.append((conn, ch, queue))
                logger.info("Bus consumer started on queue %s", queue)
                ch.start_consuming()
            except Exception:
                logger.exception("Bus consumer on queue %s stopped", queue)
            finally:
                self._running = False
                self._consumers = [c for c in self._consumers if c[2] != queue]
                try:
                    if ch is not None:
                        ch.close()
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass

        t = threading.Thread(target=_run, daemon=True, name=f"bus-{queue}")
        t.start()

    def start_consumers(
        self,
        workflow_requested_cb: Callable[[Dict[str, Any]], None],
        workflow_control_cb: Callable[[Dict[str, Any]], None],
    ) -> None:
        self._running = True
        self.declare_topology()
        self.consume("workflow.executions", workflow_requested_cb, prefetch=1)
        self.consume("workflow.control", workflow_control_cb, prefetch=1)
        self.replay_failed_events()
        logger.info("EventBus consumers started")

    def shutdown(self) -> None:
        self._running = False
        for conn, ch, queue in self._consumers:
            try:
                conn.add_callback_threadsafe(lambda c=ch: c.stop_consuming())
            except Exception:
                logger.warning("Could not signal consumer on %s to stop; closing connection", queue)
                try:
                    conn.close()
                except Exception:
                    pass
        self._consumers = []
        logger.info("EventBus shutdown requested")
