from __future__ import annotations

from abc import ABC, abstractmethod


class SourceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def read(self) -> dict[str, str]: ...

    @abstractmethod
    def source_type(self) -> str: ...