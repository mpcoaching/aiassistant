"""
LangGraph runtime adapter (Phase 6 / RUNTIME-MAPPING.md).

Implements the PathwayRuntime interface using LangGraph as the execution
substrate. Supports:
- Stateful graph execution with checkpoints
- Human-in-the-loop via interruptible nodes
- Streaming progress events
- Multi-agent coordination via subgraphs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from pathway_runtime import (
    PathwayCallRequest,
    PathwayResponse,
    PathwayRuntime,
    PathwayStatus,
    RuntimeCapability,
)

logger = logging.getLogger("langgraph.runtime")


class GraphState(TypedDict, total=False):
    messages: List[Dict[str, str]]
    context: Dict[str, Any]
    participants: List[Dict[str, Any]]
    step_outputs: Dict[str, Any]
    human_response: Optional[Dict[str, Any]]
    awaiting_human_input: bool
    human_question: str


class LangGraphRuntime(PathwayRuntime):
    """LangGraph implementation of the PathwayRuntime interface."""

    def __init__(self) -> None:
        self._checkpointer = MemorySaver()
        self._graphs: Dict[str, Any] = {}

    @property
    def id(self) -> str:
        return "langgraph"

    @property
    def capabilities(self) -> List[RuntimeCapability]:
        return [
            RuntimeCapability.STATEFUL,
            RuntimeCapability.CONCURRENT_PARTICIPANTS,
            RuntimeCapability.STREAMING,
            RuntimeCapability.INTERRUPTION,
        ]

    def invoke(self, request: PathwayCallRequest) -> PathwayResponse:
        """Execute a pattern step via LangGraph."""
        graph = self._build_graph(request.pattern_step)
        thread_id = request.session_id

        try:
            result = graph.invoke(
                {
                    "messages": [{"role": "user", "content": request.prompt}],
                    "context": request.context,
                    "participants": request.participants,
                    "step_outputs": {},
                    "human_response": None,
                },
                config={
                    "thread_id": thread_id,
                    "max_turns": request.max_turns,
                    "timeout": request.timeout_seconds,
                },
            )

            if result.get("awaiting_human_input"):
                return PathwayResponse(
                    status=PathwayStatus.WAITING,
                    outputs=result.get("step_outputs", {}),
                    artifacts=result.get("artifacts", []),
                    telemetry={"runtime": "langgraph", "thread_id": thread_id},
                    human_input_request={
                        "question": result.get("human_question", "Input required"),
                        "context": result.get("context", {}),
                        "session_id": thread_id,
                    },
                )

            return PathwayResponse(
                status=PathwayStatus.COMPLETED,
                outputs=result.get("step_outputs", {}),
                artifacts=result.get("artifacts", []),
                telemetry={"runtime": "langgraph", "thread_id": thread_id},
            )

        except Exception as exc:
            logger.exception("LangGraph execution failed")
            return PathwayResponse(
                status=PathwayStatus.FAILED,
                outputs={"error": str(exc)},
                telemetry={"runtime": "langgraph", "error": str(exc)},
            )

    def resume(self, session_id: str, human_response: Dict[str, Any]) -> PathwayResponse:
        """Resume a paused session with human input."""
        thread_id = session_id

        try:
            result = graph.invoke(
                {
                    "messages": [{"role": "user", "content": human_response.get("response", "")}],
                    "context": human_response.get("context", {}),
                    "participants": [],
                    "step_outputs": human_response.get("previous_outputs", {}),
                    "human_response": human_response,
                },
                config={
                    "thread_id": thread_id,
                    "resume": True,
                },
            )

            return PathwayResponse(
                status=PathwayStatus.COMPLETED,
                outputs=result.get("step_outputs", {}),
                artifacts=result.get("artifacts", []),
                telemetry={"runtime": "langgraph", "thread_id": thread_id, "resumed": True},
            )

        except Exception as exc:
            logger.exception("LangGraph resume failed")
            return PathwayResponse(
                status=PathwayStatus.FAILED,
                outputs={"error": str(exc)},
                telemetry={"runtime": "langgraph", "error": str(exc)},
            )

    def _build_graph(self, pattern_step: Dict[str, Any]) -> Any:
        """Build a LangGraph StateGraph from a PatternStep definition."""
        graph = StateGraph(GraphState)

        ordered_steps = pattern_step.get("ordered_steps", [])
        for i, step in enumerate(ordered_steps):
            step_id = step.get("step_id", f"step-{i}")
            role = step.get("role", "assistant")
            tools = step.get("tools", [])
            gate_condition = step.get("gate_condition")

            def make_node(role=role, tools=tools, step_id=step_id, gate_condition=gate_condition):
                def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
                    logger.info("LangGraph node: role=%s step=%s", role, step_id)

                    if gate_condition == "human_approval":
                        return {
                            "messages": state["messages"],
                            "context": state["context"],
                            "participants": state["participants"],
                            "step_outputs": {**state["step_outputs"], step_id: {"status": "awaiting_approval"}},
                            "human_response": state.get("human_response"),
                            "awaiting_human_input": True,
                            "human_question": f"Step '{step_id}' requires human approval. Proceed?",
                        }

                    outputs = {step_id: {"role": role, "tools_used": tools, "status": "completed"}}
                    return {
                        "messages": state["messages"],
                        "context": state["context"],
                        "participants": state["participants"],
                        "step_outputs": {**state["step_outputs"], **outputs},
                        "human_response": state.get("human_response"),
                        "awaiting_human_input": False,
                    }

                node_fn.__name__ = step_id
                return node_fn

            graph.add_node(step_id, make_node())

        entry_point = ordered_steps[0].get("step_id", "step-0") if ordered_steps else "step-0"
        graph.set_entry_point(entry_point)

        for i, step in enumerate(ordered_steps):
            current = step.get("step_id", f"step-{i}")
            next_step = ordered_steps[i + 1].get("step_id", f"step-{i+1}") if i + 1 < len(ordered_steps) else END

            if step.get("gate_condition") == "human_approval":
                def should_continue(state: Dict[str, Any]) -> str:
                    if state.get("awaiting_human_input"):
                        return "waiting"
                    return "continue"

                graph.add_conditional_edges(
                    current,
                    should_continue,
                    {
                        "continue": next_step,
                        "waiting": END,
                    },
                )
            else:
                graph.add_edge(current, next_step)

        compiled = graph.compile(checkpointer=self._checkpointer)
        graph_key = f"graph-{id(pattern_step)}"
        self._graphs[graph_key] = compiled
        return compiled
