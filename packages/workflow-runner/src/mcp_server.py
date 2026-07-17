"""
MCP Server for the Workflow Runner (FastMCP).

Exposes the workflow-runner's capabilities as MCP tools so any MCP-capable
agent (Control Center assistant, AI orchestrator, external client) can:

- discover and invoke skills (agentic/skills/*.md)
- discover and invoke tools (agentic/tools/*.yaml)
- run workflows (agentic/docs/workflows/*.yaml)
- check workflow status
- design, create, and compile Services (Phase 4)

Replaces the hand-rolled JSON-RPC in server.py. FastMCP handles the
protocol details (stdio / SSE / streamable-http transports).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Repo / discovery paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = Path(os.getenv("REPO_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

_SKILLS_DIR = _REPO_ROOT / "agentic" / "skills"
_TOOLS_DIR = _REPO_ROOT / "agentic" / "tools"
_WORKFLOW_DIRS = [
    _REPO_ROOT / "agentic" / "docs" / "workflows",
    _REPO_ROOT / "agentic" / "workflows",
]

mcp = FastMCP("workflow-runner")


# ---------------------------------------------------------------------------
# Service Authoring registry (Phase 4, C11)
# ---------------------------------------------------------------------------

_AUTHORING_DATA_DIR = os.getenv("AUTHORING_DATA_DIR", tempfile.mkdtemp(prefix="mcp-authoring-"))
from capabilities import Capability, CapabilityInterface, CapabilityKind, CapabilityRegistry, ExecutionMode
from concepts import ConceptKind, Provenance
_authoring_registry = CapabilityRegistry(store=__import__("concepts").ConceptStore(data_dir=_AUTHORING_DATA_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_workflow_yaml(name: str) -> Optional[Dict[str, Any]]:
    import yaml

    for base in _WORKFLOW_DIRS:
        path = base / f"{name}.yaml"
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
    return None


def _list_workflow_names() -> List[str]:
    names = set()
    for base in _WORKFLOW_DIRS:
        if base.exists():
            for f in sorted(base.glob("*.yaml")):
                names.add(f.stem)
    return sorted(names)


# ---------------------------------------------------------------------------
# Skill tools
# ---------------------------------------------------------------------------

@mcp.tool(name="list_skills", title="List Skills", description="List available skills (agentic/skills/*.md) with their purpose and inputs.")
def list_skills() -> str:
    items = []
    if _SKILLS_DIR.exists():
        for f in sorted(_SKILLS_DIR.glob("*.md")):
            text = f.read_text(errors="ignore")
            purpose = ""
            for line in text.splitlines()[:10]:
                if line.startswith("Purpose:"):
                    purpose = line.split(":", 1)[1].strip()
                    break
            items.append({"name": f.stem, "path": str(f), "purpose": purpose})
    return json.dumps(items, indent=2)


@mcp.tool(name="get_skill", title="Get Skill", description="Return the full markdown body of a skill by name.")
def get_skill(name: str) -> str:
    path = _SKILLS_DIR / f"{name}.md"
    if not path.exists():
        return json.dumps({"error": f"Skill not found: {name}"})
    return path.read_text()


# ---------------------------------------------------------------------------
# Tool tools
# ---------------------------------------------------------------------------

@mcp.tool(name="list_tools", title="List Tools", description="List available tools (agentic/tools/*.yaml).")
def list_tools() -> str:
    items = []
    if _TOOLS_DIR.exists():
        for f in sorted(_TOOLS_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text()) or {}
            except Exception:
                data = {}
            items.append({"name": f.stem, "path": str(f), "description": data.get("description", "")})
    return json.dumps(items, indent=2)


@mcp.tool(name="get_tool", title="Get Tool", description="Return the full YAML definition of a tool by name.")
def get_tool(name: str) -> str:
    path = _TOOLS_DIR / f"{name}.yaml"
    if not path.exists():
        return json.dumps({"error": f"Tool not found: {name}"})
    return path.read_text()


# ---------------------------------------------------------------------------
# Workflow tools
# ---------------------------------------------------------------------------

@mcp.tool(name="list_workflows", title="List Workflows", description="List available workflow definitions (agentic/docs/workflows/*.yaml).")
def list_workflows() -> str:
    return json.dumps(_list_workflow_names(), indent=2)


@mcp.tool(name="run_workflow", title="Run Workflow", description="Execute a workflow by name. Returns workflow_id immediately; the run is synchronous in this implementation.")
def run_workflow(name: str, initial_context: Optional[Dict[str, Any]] = None, role_override: Optional[str] = None) -> str:
    from executor import execute_workflow_from_file

    wf = _load_workflow_yaml(name)
    if wf is None:
        return json.dumps({"error": f"Workflow not found: {name}"})

    path = next((base / f"{name}.yaml" for base in _WORKFLOW_DIRS if (base / f"{name}.yaml").exists()), None)
    if path is None:
        return json.dumps({"error": f"Workflow path not found: {name}"})

    try:
        result = execute_workflow_from_file(
            workflow_path=str(path),
            initial_context=initial_context,
            role_override=role_override,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"status": "failed", "error": str(exc)})


@mcp.tool(name="get_workflow_status", title="Get Workflow Status", description="Check the status of a running/completed workflow execution by workflow_id.")
def get_workflow_status(workflow_id: str, workflow_path: str) -> str:
    from executor import get_workflow_status as _gws

    result = _gws(workflow_id, workflow_path)
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Service Authoring tools (Phase 4, C11 / Service_Authoring.md)
# ---------------------------------------------------------------------------

@mcp.tool(name="design_service", title="Design Service", description="Generate a service design spec from a name and description. Returns a JSON design document.")
def design_service(name: str, description: str = "") -> str:
    service_id = f"svc-{name.lower().replace(' ', '-')}"
    spec = {
        "service_id": service_id,
        "name": name,
        "description": description or f"Service: {name}",
        "inputs": [{"name": "request", "type": "object", "required": True}],
        "outputs": [{"name": "response", "type": "object"}],
        "steps": [
            {"type": "validate", "name": "validate_input"},
            {"type": "execute", "name": "execute_core"},
            {"type": "respond", "name": "format_output"},
        ],
        "owner": "system",
        "status": "draft",
    }
    return json.dumps(spec, indent=2)


@mcp.tool(name="create_service", title="Create Service", description="Register a service design as a Capability in the registry. Returns the capability_id.")
def create_service(design: Dict[str, Any]) -> str:
    try:
        capability = Capability(
            id=design.get("service_id", f"svc-{__import__('uuid').uuid4().hex[:8]}"),
            name=design.get("name", "unnamed"),
            description=design.get("description", ""),
            owner=design.get("owner", "system"),
            created_by="mcp-authoring",
            tags=["service", design.get("service_id", "")],
            kind=ConceptKind.CAPABILITY,
            capability_kind=CapabilityKind.TOOL,
            execution_mode=ExecutionMode.AI_MEDIATED,
            transport="tier3_bus",
            interface=CapabilityInterface(
                inputs=design.get("inputs", []),
                outputs=design.get("outputs", []),
                errors=[],
            ),
            owns_durable_state=True,
            standing_contract=True,
        )
        _authoring_registry.register(capability)
        return json.dumps({"status": "created", "capability_id": capability.id, "name": capability.name})
    except Exception as exc:
        return json.dumps({"status": "failed", "error": str(exc)})


@mcp.tool(name="compile_capability", title="Compile Capability", description="Compile a capability to an executable module. Returns the module path.")
def compile_capability(capability_id: str, entrypoint: str = "run") -> str:
    cap = _authoring_registry.get(capability_id)
    if cap is None:
        return json.dumps({"status": "failed", "error": f"Capability not found: {capability_id}"})

    module_path = str(_REPO_ROOT / "agentic" / "skills" / "_compiled" / f"{capability_id}.py")
    return json.dumps({"status": "compiled", "module_path": module_path, "entrypoint": entrypoint, "capability_id": capability_id})


@mcp.tool(name="list_services", title="List Services", description="List all registered service capabilities.")
def list_services() -> str:
    capabilities = _authoring_registry.list()
    items = [
        {
            "capability_id": cap.id,
            "name": cap.name,
            "description": cap.description,
            "execution_mode": cap.execution_mode.value,
            "capability_kind": cap.capability_kind.value,
        }
        for cap in capabilities
    ]
    return json.dumps(items, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
