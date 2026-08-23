"""
Adapter: contracts.CapabilityDiscoveryPort -> CapabilityRegistry + CapabilityMatcher.

Wraps CapabilityRegistry.list_all() and CapabilityMatcher.match()
to produce CapabilityCandidate lists.
"""

from __future__ import annotations

from typing import Any

from contracts.capability_discovery import CapabilityCandidate
from capabilities import CapabilityRegistry
from capability_matcher import CapabilityMatcher
from capability import Capability
from enterprise_context import ContextRecord


class CapabilityDiscoveryAdapter:
    def __init__(self, registry: CapabilityRegistry, matcher: CapabilityMatcher) -> None:
        self._registry = registry
        self._matcher = matcher

    def list_capabilities(self) -> list[CapabilityCandidate]:
        return [self._to_candidate(cap) for cap in self._registry.list()]

    def find_capabilities(self, request_text: str, context: dict[str, Any]) -> list[CapabilityCandidate]:
        capabilities = self._registry.list()
        ctx = ContextRecord(**context) if context else ContextRecord()
        match_result = self._matcher.match(request_text, ctx, capabilities)
        return [self._to_candidate(cap) for cap in match_result.candidates]

    def _to_candidate(self, capability: Capability) -> CapabilityCandidate:
        return CapabilityCandidate(
            id=capability.id,
            name=capability.name,
            description=capability.description,
            kind=capability.capability_kind.value,
            tags=list(capability.tags),
            execution_mode=capability.payload.get("execution_mode", "ai_mediated"),
        )
