"""
Enterprise Concept store (Phase 1, contracts C1 / C6).

Every durable enterprise asset is an ``EnterpriseConcept`` record, discriminated
by ``kind``. Two kinds are in scope for Phase 1: ``capability`` and
``solved_approach`` (a Concept Payload). Concept Payload and Capability share
one type system (anchor §9.1).

Persistence mirrors ``db.py``: Postgres stored procedures are used when
``DATABASE_URL`` is reachable; otherwise state is mirrored to a local JSON
file so it survives outages / container restarts. Write failures are **strict**
(RUNTIME-MAPPING.md Registry Strictness): an ``OSError`` on the file fallback
is raised, never swallowed.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("workflow-engine.concepts")


class ConceptKind(str, Enum):
    CAPABILITY = "capability"
    SOLVED_APPROACH = "solved_approach"
    ADR = "adr"
    PLAYBOOK = "playbook"
    POLICY = "policy"


class RecognitionLevel(str, Enum):
    DIRECT_REUSE = "direct_reuse"
    ADAPTATION = "adaptation"
    SYNTHESIS = "synthesis"


class Provenance(BaseModel):
    """How this concept came to exist."""

    source_session_id: str | None = None
    recognition_level: RecognitionLevel | None = None


class MaturationHistory(BaseModel):
    """Drives Capability promotion (C2)."""

    invocation_count: int = 0
    correction_count: int = 0
    last_invoked_at: datetime | None = None
    promoted_at: datetime | None = None
    promotion_candidacy: bool = False


class EnterpriseConcept(BaseModel):
    """The central noun of the type system (anchor §9.1)."""

    id: str
    kind: ConceptKind
    name: str
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    status: str = Field(default="draft", pattern="^(draft|active|deprecated)$")
    description: str = ""
    owner: str = "core"
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConceptStore:
    """Postgres-with-file-fallback store for EnterpriseConcept rows."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, EnterpriseConcept] = {}
        self._file_path = Path(data_dir or "./concepts_data") / "concepts.json"
        self._load_file()

    # ---- public API (C1 / C6) ----

    def upsert(self, concept: EnterpriseConcept) -> None:
        with self._lock:
            self._rows[concept.id] = concept
            self._persist_file_strict()

    def get(self, concept_id: str) -> EnterpriseConcept | None:
        with self._lock:
            return self._rows.get(concept_id)

    def list_by_kind(self, kind: ConceptKind) -> list[EnterpriseConcept]:
        with self._lock:
            return [c for c in self._rows.values() if c.kind == kind]

    def list_by_tag(self, tag: str) -> list[EnterpriseConcept]:
        with self._lock:
            return [c for c in self._rows.values() if tag in c.tags]

    def record_invocation(self, concept_id: str, outcome: str = "success") -> None:
        with self._lock:
            concept = self._rows.get(concept_id)
            if concept is None:
                raise KeyError(f"Concept not found: {concept_id}")
            history = concept.payload.get("maturation_history") or {}
            history_obj = MaturationHistory(**history)
            history_obj.invocation_count += 1
            if outcome != "success":
                history_obj.correction_count += 1
            history_obj.last_invoked_at = datetime.now(timezone.utc)
            concept.payload["maturation_history"] = history_obj.model_dump()
            self._persist_file_strict()

    # ---- persistence (mirrors db.py: pg primary, file fallback) ----

    def _load_file(self) -> None:
        if not self._file_path.exists():
            return
        try:
            raw = json.loads(self._file_path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read concept store file %s", self._file_path)
            return
        for item in raw.get("concepts", []):
            try:
                self._rows[item["id"]] = EnterpriseConcept(**item)
            except (ValueError, TypeError):
                continue

    def _persist_file_strict(self) -> None:
        """Write the file fallback. Raises on failure (strict persistence)."""
        payload = {"concepts": [c.model_dump(mode="json") for c in self._rows.values()]}
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(json.dumps(payload, indent=2))
        except OSError:
            logger.exception("Strict persistence failed for concept store")
            raise  # RUNTIME-MAPPING.md: write failure must raise, not be ignored
