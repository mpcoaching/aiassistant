"""
Tests for skill_runtime.run_skill — the canonical, tier-agnostic skill
execution entry point used by compiled skill modules.

Behaviour verified: composes a prompt from the skill spec and invokes the LLM
runtime, returning its result. Externals (composer, runtime) are mocked.
"""

from unittest.mock import patch

from skill_runtime import run_skill


def test_run_skill_composes_prompt_and_calls_runtime():
    context = {"brief": "design a service"}
    with patch(
        "skill_runtime.compose_skill_prompt",
        return_value="# Skill: alpha\ncompose me",
    ) as mock_compose, patch(
        "runtime_client.run",
        return_value={"status": "completed", "output": {"ok": True}},
    ) as mock_run:
        result = run_skill("alpha", context, role="developer")

    mock_compose.assert_called_once()
    mock_run.assert_called_once_with("# Skill: alpha\ncompose me")
    assert result == {"status": "completed", "output": {"ok": True}}


def test_run_skill_accepts_none_context():
    with patch("skill_runtime.compose_skill_prompt", return_value="p"), patch(
        "runtime_client.run", return_value={"status": "completed"}
    ):
        result = run_skill("alpha")
    assert result == {"status": "completed"}
