"""
MCP Server for the Workflow Runner.

Exposes workflow execution as MCP tools that any MCP-capable agent can call.

MCP Tools:
- run_workflow: Execute a workflow YAML file
- get_workflow_status: Check the status of a running/completed workflow
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure the script's directory is on sys.path so relative imports work
# regardless of what cwd the MCP client launches from
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# The repo root is two levels up from the server.py file
# (server.py is in agentic/src/workflow-runner/)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_script_dir)))

from executor import execute_workflow_from_file, get_workflow_status


def main() -> None:
    """
    MCP server entry point.

    Reads JSON-RPC requests from stdin and writes responses to stdout,
    following the MCP protocol for stdio-based transport.
    """
    # Signal that the server is ready
    _send_response({
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "run_workflow": {
                        "name": "run_workflow",
                        "description": "Execute a workflow YAML file. Composes prompts from Role + Skill files and executes each step sequentially.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "workflow_path": {
                                    "type": "string",
                                    "description": "Path to the workflow YAML file (e.g., 'agentic/docs/workflows/architecture.solution.create.yaml')"
                                },
                                "initial_context": {
                                    "type": "object",
                                    "description": "Optional initial context values (key-value pairs passed to steps)",
                                    "additionalProperties": True
                                },
                                "role_override": {
                                    "type": "string",
                                    "description": "Optional role name to use for all skill steps (overrides workflow role)"
                                }
                            },
                            "required": ["workflow_path"]
                        }
                    },
                    "get_workflow_status": {
                        "name": "get_workflow_status",
                        "description": "Get the current status of a running or completed workflow execution.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "workflow_id": {
                                    "type": "string",
                                    "description": "The workflow execution ID returned by run_workflow"
                                },
                                "workflow_path": {
                                    "type": "string",
                                    "description": "Path to the workflow YAML file"
                                }
                            },
                            "required": ["workflow_id", "workflow_path"]
                        }
                    }
                }
            }
        },
        "id": 1
    })

    # Main request loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name == "run_workflow":
                result = _handle_run_workflow(tool_args)
                _send_response({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id,
                })
            elif tool_name == "get_workflow_status":
                result = _handle_get_status(tool_args)
                _send_response({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id,
                })
            else:
                _send_response({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}",
                    },
                    "id": request_id,
                })

        elif method == "initialize":
            # Already sent capabilities above; acknowledge
            _send_response({
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    }
                },
                "id": request_id,
            })

        elif method == "notifications/initialized":
            # No-op, client is ready
            pass

        elif method == "shutdown":
            _send_response({
                "jsonrpc": "2.0",
                "result": None,
                "id": request_id,
            })
            break

        else:
            _send_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
                "id": request_id,
            })


def _handle_run_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a run_workflow tool call."""
    workflow_path = args.get("workflow_path", "")
    initial_context = args.get("initial_context", {})
    role_override = args.get("role_override")

    if not workflow_path:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "status": "failed",
                        "error": "workflow_path is required",
                    }, indent=2),
                }
            ],
            "isError": True,
        }

    # Resolve relative path from project root
    resolved_path = Path(workflow_path)
    if not resolved_path.exists():
        # Try relative to current directory
        resolved_path = Path.cwd() / workflow_path
        if not resolved_path.exists():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "failed",
                            "error": f"Workflow file not found: {workflow_path}",
                        }, indent=2),
                    }
                ],
                "isError": True,
            }

    result = execute_workflow_from_file(
        workflow_path=str(resolved_path),
        initial_context=initial_context or None,
        role_override=role_override,
    )

    # Format the result for the MCP response
    is_error = result.get("status") == "failed"

    # For skill steps, include the composed prompts so the agent can execute them
    output_text = json.dumps(result, indent=2, default=str)

    return {
        "content": [
            {
                "type": "text",
                "text": output_text,
            }
        ],
        "isError": is_error,
    }


def _handle_get_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a get_workflow_status tool call."""
    workflow_id = args.get("workflow_id", "")
    workflow_path = args.get("workflow_path", "")

    if not workflow_id or not workflow_path:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": "workflow_id and workflow_path are required",
                    }, indent=2),
                }
            ],
            "isError": True,
        }

    result = get_workflow_status(workflow_id, workflow_path)

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2, default=str),
            }
        ],
        "isError": not result.get("found", True),
    }


def _send_response(response: Dict[str, Any]) -> None:
    """Send a JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()