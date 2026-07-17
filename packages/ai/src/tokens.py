"""
Token Economics (Phase 5, contract C13 / anchor §11).

Tracks token usage and cost per session, per capability, and per model.
Costs are computed from a static rate table; production swaps in live pricing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---- models ----------------------------------------------------------------

class TokenUsage(BaseModel):
    session_id: str
    capability_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = "unknown"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CostAccrual(BaseModel):
    session_id: str
    capability_id: str
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    model: str = "unknown"
    currency: str = "USD"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# v1 rate table (USD per 1K tokens)
_RATE_TABLE: Dict[str, tuple[float, float]] = {
    "gpt-4": (0.03, 0.06),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0015, 0.002),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet": (0.003, 0.015),
}


class TokenEconomics:
    """Accrues token usage and computes cost."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = Path(data_dir or ".")
        self._usages: List[TokenUsage] = []
        self._accruals: List[CostAccrual] = []
        self._load()

    def accrue(
        self,
        session_id: str,
        capability_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "unknown",
    ) -> CostAccrual:
        total = prompt_tokens + completion_tokens
        usage = TokenUsage(
            session_id=session_id,
            capability_id=capability_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            model=model,
        )
        self._usages.append(usage)

        prompt_rate, completion_rate = _RATE_TABLE.get(model, (0.001, 0.002))
        prompt_cost = (prompt_tokens / 1000.0) * prompt_rate
        completion_cost = (completion_tokens / 1000.0) * completion_rate
        total_cost = prompt_cost + completion_cost

        accrual = CostAccrual(
            session_id=session_id,
            capability_id=capability_id,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            model=model,
        )
        self._accruals.append(accrual)
        self._persist()
        return accrual

    def session_cost(self, session_id: str) -> float:
        return sum(a.total_cost for a in self._accruals if a.session_id == session_id)

    def capability_cost(self, capability_id: str) -> float:
        return sum(a.total_cost for a in self._accruals if a.capability_id == capability_id)

    def total_cost(self) -> float:
        return sum(a.total_cost for a in self._accruals)

    # ---- persistence ----

    def _load(self) -> None:
        path = self._data_dir / "token_economics.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text())
            for item in raw.get("accruals", []):
                self._accruals.append(CostAccrual(**item))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    def _persist(self) -> None:
        path = self._data_dir / "token_economics.json"
        payload = {
            "accruals": [a.model_dump(mode="json") for a in self._accruals],
        }
        try:
            path.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass
