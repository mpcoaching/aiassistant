"""
Registry Configuration Contract.

Defines the configuration required for registry authentication.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class RegistryConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    username: str = Field(validation_alias="REGISTRY_USER")
    password: str = Field(validation_alias="REGISTRY_PASSWORD")
    endpoint: str = Field(default="https://registry.local.test", validation_alias="REGISTRY_ENDPOINT")

    @classmethod
    def type_id(cls) -> str:
        return "registry-credentials"

    @classmethod
    def purpose(cls) -> str:
        return "Credentials for the local Docker registry"

    @classmethod
    def owner(cls) -> str:
        return "ci-worker"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="ci-worker", execution="ci-build")

    @classmethod
    def documentation(cls) -> str:
        return "Registry authentication credentials for pulling/pushing container images"