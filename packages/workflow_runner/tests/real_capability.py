"""Real capability module for Increment 21T proof.

This module provides a simple executable capability that the worker can
invoke through CapabilityExecutionPort to prove the real end-to-end path:
  User → Chat → Assistant (inside Organisation) → Organisation Control Plane → Worker → CapabilityExecutionPort → Capability → Result
"""


def run(context: dict[str, Any]) -> dict[str, Any]:
    """Execute the capability.

    Args:
        context: Execution context from the work item

    Returns:
        Result dict with status, message, and echoed context
    """
    return {
        "status": "completed",
        "message": "Real capability executed successfully via CapabilityExecutionPort",
        "received_context": context,
        "capability": "real_capability",
    }
