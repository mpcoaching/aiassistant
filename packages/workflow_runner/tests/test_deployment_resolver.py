"""
Tests for DeploymentResolver (Increment 17).
"""

from __future__ import annotations

import pytest

from capability_deployment import CapabilityDeployment, ExecutionMode, Transport
from deployment_resolver import DeploymentNotFoundError, DeploymentResolver


def _deployment(capability_id: str, environment: str) -> CapabilityDeployment:
    return CapabilityDeployment(
        capability_id=capability_id,
        environment=environment,
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=None,
        ai_spec=None,
    )


def test_resolve_returns_matching_deployment() -> None:
    resolver = DeploymentResolver()
    deployment = _deployment("cap-1", "prod")
    resolver.register(deployment)
    resolved = resolver.resolve("cap-1", "prod")
    assert resolved.capability_id == "cap-1"
    assert resolved.environment == "prod"


def test_resolve_raises_when_missing() -> None:
    resolver = DeploymentResolver()
    with pytest.raises(DeploymentNotFoundError) as exc_info:
        resolver.resolve("cap-missing", "prod")
    assert "cap-missing" in str(exc_info.value)
    assert "prod" in str(exc_info.value)


def test_same_capability_different_environments() -> None:
    resolver = DeploymentResolver()
    prod = _deployment("cap-1", "prod")
    dev = _deployment("cap-1", "dev")
    resolver.register(prod)
    resolver.register(dev)
    assert resolver.resolve("cap-1", "prod") is prod
    assert resolver.resolve("cap-1", "dev") is dev


def test_ambiguous_duplicate_deployment_raises() -> None:
    resolver = DeploymentResolver()
    resolver.register(_deployment("cap-1", "prod"))
    resolver.register(_deployment("cap-1", "prod"))
    with pytest.raises(ValueError, match="Ambiguous deployments"):
        resolver.resolve("cap-1", "prod")


def test_empty_resolver_raises() -> None:
    resolver = DeploymentResolver()
    with pytest.raises(DeploymentNotFoundError):
        resolver.resolve("cap-1", "prod")
