from __future__ import annotations

from pydantic import BaseModel


class ResolvedContract(BaseModel):
    name: str
    version: str
    configuration: dict[str, str]
    validated_at: str | None = None