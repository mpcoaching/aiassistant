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
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pika

logger = logging.getLogger("workflow-engine.bus")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
WORKFLOW_EXCHANGE = "workflow.mode"
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


def _event_envelope(event_type: str, workflow_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": payload.get("event_id") or str(__import__("uuid").uuid4()),
        "event_type": event_type,
        "timestamp": __import__("datetime").datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow_id,
        "correlation_id": payload.get("correlation_id"),
        "payload": payload,
    }


class EventBus:
    def __init__(self, url: str = RABBITMQ_URL) -> None:
        self._url = url
        self._lock = threading.Lock()
        self._consumer_thread: Optional[threading.Thread] = None
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
                ch.exchange_declare(exchange=WORKFLOW_EXCHANGE, exchange_type="topic", durable=True)
                ch.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="topic", durable=True)

                for queue_name, routing_keys in WORKFLOW_QUEUES.items():
                    ch.queue_declare(queue=queue_name, durable=True, arguments={
                        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
                        "x-dead-letter-routing-key": f"dead.{queue_name}",
                    })
                    for rk in routing_keys:
                        ch.queue_bind(exchange=WORKFLOW_EXCHANGE, queue=queue_name, routing_key=rk)

                ch.queue_declare(queue="workflow.dead", durable=True)
                ch.queue_bind(exchange=DEAD_LETTER_EXCHANGE, queue="workflow.dead", routing_key="dead.#")
                ch.close()
            finally:
                conn.close()

    def publish(self, routing_key: str, event_type: str, workflow_id: str, payload: Dict[str, Any]) -> None:
        envelope = _event_envelope(event_type, workflow_id, payload)
        body = json.dumps(envelope).encode("utf-8")
        with self._lock:
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
            except Exception:
                logger.exception("Failed to publish event %s", event_type)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

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
        def _run() -> None:
            conn = self._connect()
            ch = conn.channel()
            ch.basic_qos(prefetch_count=prefetch)

            def on_message(ch_method, properties, body):  # noqa: A003
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

            ch.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=False)
            logger.info("Bus consumer started on queue %s", queue)
            try:
                ch.start_consuming()
            except Exception:
                logger.exception("Bus consumer stopped")
            finally:
                try:
                    ch.close()
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
        logger.info("EventBus consumers started")

    def shutdown(self) -> None:
        self._running = False
        logger.info("EventBus shutdown requested")
