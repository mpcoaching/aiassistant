from typing import Protocol, Any
from pydantic import BaseModel


class PreviousSolution(BaseModel):
    concept_id: str
    name: str
    summary: str
    invocation_count: int
    last_invoked: str | None = None


class SolutionRecord(BaseModel):
    summary: str = ""
    outputs: dict[str, Any] = {}
    strategy: str = ""
    pattern_pipeline: list[str] = []
    invocation_count: int = 1


class EnterpriseInformationPort(Protocol):
    def find_previous_solutions(self, strategy_tag: str) -> PreviousSolution | None: ...
    def record_solution(self, solution: SolutionRecord) -> None: ...
