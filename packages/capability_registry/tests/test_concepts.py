"""
TDD tests for the Enterprise Concept store (Phase 1, contracts C1/C6).

These tests are written first and define the behaviour the implementation must
satisfy. The store routes through Postgres stored procedures when available
and falls back to a local JSONL/JSON file so state survives outages, mirroring
the db.py pattern already used for workflow state.

Behaviour requirements (from SA-CONTRACTS-PHASE1.md C1, C6):
- upsert/get/list by kind / by tag
- one type system: Capability and ConceptPayload are EnterpriseConcept rows
  discriminated by `kind`
- strict persistence: write failure must raise, not be swallowed
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from concepts import (
    ConceptKind,
    EnterpriseConcept,
    MaturationHistory,
    Provenance,
    ConceptStore,
)


def _now() -> datetime:
    return datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)


_cap_counter = {"n": 0}


def _make_capability(name: str, **kw) -> EnterpriseConcept:
    _cap_counter["n"] += 1
    return EnterpriseConcept(
        id=kw.pop("id", f"cap-{_cap_counter['n']:03d}"),
        kind=ConceptKind.CAPABILITY,
        name=name,
        version_major=1,
        version_minor=0,
        version_patch=0,
        status="active",
        description=kw.pop("description", f"{name} capability"),
        owner=kw.pop("owner", "core"),
        created_by=kw.pop("created_by", "assistant_reasoning"),
        created_at=kw.pop("created_at", _now()),
        tags=kw.pop("tags", ["tool"]),
        provenance=kw.pop("provenance", Provenance()),
        payload=kw.pop("payload", {}),
    )


# ---- upsert / get round-trip ------------------------------------------------

def test_upsert_then_get_roundtrip(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    cap = _make_capability("work_session")
    store.upsert(cap)
    got = store.get(cap.id)
    assert got is not None
    assert got.name == "work_session"
    assert got.kind == ConceptKind.CAPABILITY


def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    assert store.get("does-not-exist") is None


def test_upsert_overwrites_same_id(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    cap = _make_capability("lead_enrichment", description="v1")
    store.upsert(cap)
    cap2 = _make_capability("lead_enrichment", description="v2", id=cap.id)
    store.upsert(cap2)
    assert store.get(cap.id).description == "v2"
    # only one row for that id
    assert len(store.list_by_kind(ConceptKind.CAPABILITY)) == 1


# ---- list by kind / tag -----------------------------------------------------

def test_list_by_kind(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    store.upsert(_make_capability("a", tags=["tool"]))
    store.upsert(_make_capability("b", tags=["tool"]))
    store.upsert(
        EnterpriseConcept(
            id="cp-1",
            kind=ConceptKind.SOLVED_APPROACH,
            name="pci-sop",
            version_major=1,
            version_minor=0,
            version_patch=0,
            status="active",
            description="PCI SOP",
            owner="core",
            created_by="system",
            created_at=_now(),
            tags=["sop"],
            provenance=Provenance(),
            payload={"approach": "restart gateway"},
        )
    )
    caps = store.list_by_kind(ConceptKind.CAPABILITY)
    assert {c.name for c in caps} == {"a", "b"}
    approaches = store.list_by_kind(ConceptKind.SOLVED_APPROACH)
    assert len(approaches) == 1


def test_list_by_tag(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    store.upsert(_make_capability("a", tags=["tool", "lead"]))
    store.upsert(_make_capability("b", tags=["tool"]))
    assert {c.name for c in store.list_by_tag("lead")} == {"a"}


# ---- file fallback persists ------------------------------------------------

def test_state_survives_reopen_via_file(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    cap = _make_capability("task_tracking")
    store.upsert(cap)
    # A fresh store instance (simulating a process restart / Postgres outage)
    # must still see the concept via the file fallback.
    reopened = ConceptStore(data_dir=str(tmp_path))
    assert reopened.get(cap.id) is not None
    assert reopened.get(cap.id).name == "task_tracking"


# ---- strict persistence: write failure must raise --------------------------

def test_strict_persistence_raises_on_write_failure(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    # Point the file fallback at a non-writable path to force OSError.
    store._file_path = tmp_path / "concepts.json"
    store._file_path.parent.chmod(0o000)
    cap = _make_capability("x")
    with pytest.raises(OSError):
        store.upsert(cap)
    # restore perms so pytest can clean up the tmp dir
    tmp_path.chmod(0o755)


# ---- MaturationHistory ties to Capability payload --------------------------

def test_capability_payload_carries_maturation(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    cap = _make_capability(
        "y",
        payload={
            "capability_kind": "tool",
            "execution_mode": "ai_mediated",
            "maturation_history": MaturationHistory(invocation_count=3).model_dump(),
        },
    )
    store.upsert(cap)
    got = store.get(cap.id)
    assert got.payload["maturation_history"]["invocation_count"] == 3
