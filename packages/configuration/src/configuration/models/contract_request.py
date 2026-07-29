from __future__ import annotations

from pydantic import BaseModel


class ContractRequest(BaseModel):
    capability: str