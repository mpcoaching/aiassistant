from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Lifecycle:
    platform: str
    capability: str
    execution: str


class Contract(ABC):
    @classmethod
    @abstractmethod
    def type_id(cls) -> str: ...

    @classmethod
    @abstractmethod
    def purpose(cls) -> str: ...

    @classmethod
    @abstractmethod
    def owner(cls) -> str: ...

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="", capability="", execution="")

    @classmethod
    def validation_strategy(cls) -> Any | None:
        return None

    @classmethod
    def documentation(cls) -> str:
        return ""