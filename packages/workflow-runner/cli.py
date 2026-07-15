"""
Workflow Runner CLI — command-line interface for running workflows and chains.

Subcommands:
- validate: check a workflow's required inputs and report missing ones
- run: execute a workflow, prompting for missing inputs interactively
- run-chain: detect and execute the downstream chain from a workflow
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from chain import find_downstream_chain, is_chain_workflow
from loader import load_workflow, WorkflowLoadError
from models import WorkflowDefinition
from executor import execute_workflow_from_file


def collect_required_inputs(workflow: WorkflowDefinition) -> Dict[str, Any]:
    """
    Collect required inputs for a workflow interactively from the user.

    Args:
        workflow: The workflow definition.

    Returns:
        Dictionary of input values keyed by input name.
    """
    if not workflow.inputs:
        return {}

    print(f"\nWorkflow '{workflow.name}' requires the following inputs:\n")
    answers: Dict[str, Any] = {}
    for input_name in workflow.inputs:
        value = input(f"  {input_name}: ").strip()
        answers[input_name] = value

    return answers


def validate_workflow_inputs(workflow: WorkflowDefinition) -> List[str]:
    """
    Validate that all required inputs are present in the workflow definition.

    Args:
        workflow: The workflow definition.

    Returns:
        List of missing input names (empty if all present).
    """
    if not workflow.inputs:
        return []

    # For now, we just report what inputs are required.
    # Actual values are collected at runtime via collect_required_inputs().
    return list(workflow.inputs)


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle the 'validate' subcommand."""
    try:
        workflow = load_workflow(args.workflow_path)
    except WorkflowLoadError as e:
        print(f"Error loading workflow: {e}", file=sys.stderr)
        return 1

    missing = validate_workflow_inputs(workflow)
    if missing:
        print(json.dumps({
            "status": "missing_inputs",
            "workflow": workflow.name,
            "missing_inputs": missing,
        }, indent=2))
        return 2

    print(json.dumps({
        "status": "ok",
        "workflow": workflow.name,
        "inputs": workflow.inputs or [],
    }, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Handle the 'run' subcommand."""
    try:
        workflow = load_workflow(args.workflow_path)
    except WorkflowLoadError as e:
        print(f"Error loading workflow: {e}", file=sys.stderr)
        return 1

    # Collect initial context from args or interactively
    context: Dict[str, Any] = {}
    if args.context:
        for item in args.context:
            if "=" in item:
                key, value = item.split("=", 1)
                context[key.strip()] = value.strip()

    # Prompt for any missing required inputs
    missing = validate_workflow_inputs(workflow)
    if missing:
        print(f"\nWorkflow '{workflow.name}' requires inputs. Please provide them:\n")
        for input_name in missing:
            if input_name not in context:
                value = input(f"  {input_name}: ").strip()
                context[input_name] = value

    print(f"\nRunning workflow: {workflow.name}\n")
    result = execute_workflow_from_file(
        workflow_path=args.workflow_path,
        initial_context=context or None,
        role_override=args.role,
    )

    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "completed" else 1


def cmd_run_chain(args: argparse.Namespace) -> int:
    """Handle the 'run-chain' subcommand."""
    try:
        workflow = load_workflow(args.workflow_path)
    except WorkflowLoadError as e:
        print(f"Error loading workflow: {e}", file=sys.stderr)
        return 1

    # Detect downstream chain
    chain = find_downstream_chain(workflow.name)
    is_chain = is_chain_workflow(workflow.name)

    if len(chain) == 1 and not is_chain:
        print(f"\nWorkflow '{workflow.name}' is not part of a chain.")
        print("Running it as a standalone workflow.\n")
        return cmd_run(args)

    print(f"\nDetected chain: {' -> '.join(chain)}\n")

    # Collect initial context from args
    context: Dict[str, Any] = {}
    if args.context:
        for item in args.context:
            if "=" in item:
                key, value = item.split("=", 1)
                context[key.strip()] = value.strip()

    # Run each workflow in the chain
    overall_status = 0
    for wf_name in chain:
        # Resolve the workflow file path
        wf_path = _resolve_workflow_path(wf_name)
        if wf_path is None:
            print(f"Error: workflow '{wf_name}' not found", file=sys.stderr)
            return 1

        try:
            wf = load_workflow(wf_path)
        except WorkflowLoadError as e:
            print(f"Error loading workflow '{wf_name}': {e}", file=sys.stderr)
            return 1

        # Prompt for any missing required inputs
        missing = validate_workflow_inputs(wf)
        if missing:
            print(f"\nWorkflow '{wf.name}' requires inputs. Please provide them:\n")
            for input_name in missing:
                if input_name not in context:
                    value = input(f"  {input_name}: ").strip()
                    context[input_name] = value

        print(f"\n{'='*60}")
        print(f"Running workflow: {wf.name}")
        print(f"{'='*60}\n")

        result = execute_workflow_from_file(
            workflow_path=str(wf_path),
            initial_context=context or None,
            role_override=args.role,
        )

        print(json.dumps(result, indent=2, default=str))

        if result.get("status") != "completed":
            print(f"\nChain stopped: workflow '{wf.name}' failed.", file=sys.stderr)
            return 1

        # Carry forward the context from this workflow to the next
        if result.get("context"):
            context.update(result["context"])

    print(f"\nChain completed successfully: {' -> '.join(chain)}")
    return 0


def _resolve_workflow_path(workflow_name: str) -> Optional[Path]:
    """Resolve a workflow name to a file path."""
    search_paths = [
        Path("agentic/docs/workflows"),
        Path("agentic/workflows"),
    ]
    for base in search_paths:
        for ext in ("yaml", "yml"):
            p = base / f"{workflow_name}.{ext}"
            if p.exists():
                return p
    return None


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="workflow-runner",
        description="Run workflows and workflow chains.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate workflow inputs")
    p_validate.add_argument("workflow_path", help="Path to the workflow YAML file")

    # run
    p_run = subparsers.add_parser("run", help="Run a single workflow")
    p_run.add_argument("workflow_path", help="Path to the workflow YAML file")
    p_run.add_argument("--context", "-c", action="append",
                       help="Initial context in key=value format (repeatable)")
    p_run.add_argument("--role", help="Optional role override")

    # run-chain
    p_chain = subparsers.add_parser("run-chain", help="Run a workflow and its downstream chain")
    p_chain.add_argument("workflow_path", help="Path to the workflow YAML file")
    p_chain.add_argument("--context", "-c", action="append",
                         help="Initial context in key=value format (repeatable)")
    p_chain.add_argument("--role", help="Optional role override")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "run-chain":
        return cmd_run_chain(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())