from __future__ import annotations

from configuration.providers.base import SourceProvider


def resolve_precedence(
    providers: dict[str, SourceProvider],
    precedence: list[str],
) -> list[SourceProvider]:
    ordered: list[SourceProvider] = []
    for source_type in precedence:
        if source_type in providers:
            ordered.append(providers[source_type])
    return ordered