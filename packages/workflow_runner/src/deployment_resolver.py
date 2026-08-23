"""
Operations plane — Deployment resolution (Increment 17).

Resolves a CapabilityDeployment by capability_id + environment.
Owns the deployment registry for the current process. Persistence is delegated
to an optional backing store so the abstraction remains replaceable.
"""

from __future__ import annotations

from capability_deployment import CapabilityDeployment


class DeploymentNotFoundError(Exception):
    """Raised when no deployment exists for the requested capability and environment."""

    def __init__(self, capability_id: str, environment: str) -> None:
        self.capability_id = capability_id
        self.environment = environment
        super().__init__(
            f"No deployment found for capability '{capability_id}' in environment '{environment}'"
        )


class DeploymentResolver:
    """Resolves CapabilityDeployment records by capability and environment."""

    def __init__(self, deployments: list[CapabilityDeployment] | None = None) -> None:
        self._deployments: list[CapabilityDeployment] = list(deployments or [])

    def register(self, deployment: CapabilityDeployment) -> None:
        self._deployments.append(deployment)

    def resolve(self, capability_id: str, environment: str) -> CapabilityDeployment:
        matches = [
            d
            for d in self._deployments
            if d.capability_id == capability_id and d.environment == environment
        ]
        if not matches:
            raise DeploymentNotFoundError(capability_id, environment)
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous deployments for capability '{capability_id}' in environment '{environment}': "
                f"{len(matches)} matches found"
            )
        return matches[0]
