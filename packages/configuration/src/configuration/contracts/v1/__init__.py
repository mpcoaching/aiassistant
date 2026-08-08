"""
Version 1 Configuration Contracts.

Versioned contracts allow components to declare which contract version they
support, enabling non-breaking evolution of configuration contracts.
"""

from __future__ import annotations

from configuration.contracts.base import Contract, Lifecycle
from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration
from configuration.contracts.v1.qdrant import QdrantConfiguration
from configuration.contracts.v1.registry import RegistryConfiguration

__all__ = [
    "Contract",
    "DatabaseConfiguration",
    "LangGraphRuntimeConfiguration",
    "Lifecycle",
    "MessageBusConfiguration",
    "QdrantConfiguration",
    "RegistryConfiguration",
]
