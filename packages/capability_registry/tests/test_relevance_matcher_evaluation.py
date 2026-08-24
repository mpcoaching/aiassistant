"""
Increment 21G — RelevanceMatcher evaluation corpus.

Loads a labelled evaluation corpus and computes baseline metrics
against the existing RelevanceMatcher without changing production behaviour.

Metrics:
  - Top-1 accuracy
  - Top-3 recall
  - No-match precision
  - Average candidate-set size
  - Median candidate-set size

This file is measurement-only. It does not modify the matcher,
the action policy, contracts, or any production code.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from capability_matcher import MatchResult
from capabilities import Capability, CapabilityKind, CapabilityStatus
from enterprise_context import ContextRecord
from relevance_matcher import RelevanceMatcher


_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "evaluation_corpus.json"


def _load_corpus() -> dict[str, Any]:
    with _CORPUS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_capabilities(corpus: dict[str, Any]) -> list[Capability]:
    capabilities = []
    for cap_data in corpus["capabilities"]:
        capabilities.append(
            Capability(
                id=cap_data["id"],
                name=cap_data["name"],
                description=cap_data.get("description", ""),
                owner="core",
                created_by="evaluation",
                tags=list(cap_data.get("tags", [])),
                capability_kind=CapabilityKind.TOOL,
                status=CapabilityStatus.ACTIVE,
            )
        )
    return capabilities


def _is_correct_top(
    actual_top_id: str | None,
    expected_id: str | None,
    acceptable_alternatives: list[str],
) -> bool:
    if expected_id is not None:
        return actual_top_id == expected_id
    if acceptable_alternatives:
        return actual_top_id in acceptable_alternatives
    return False


def _is_correct_top3(
    actual_top3_ids: list[str],
    expected_id: str | None,
    acceptable_alternatives: list[str],
) -> bool:
    targets: list[str] = []
    if expected_id is not None:
        targets.append(expected_id)
    targets.extend(acceptable_alternatives)
    if not targets:
        return False
    return any(t in actual_top3_ids for t in targets)


def test_relevance_matcher_evaluation() -> None:
    corpus = _load_corpus()
    capabilities = _build_capabilities(corpus)
    matcher = RelevanceMatcher()

    examples = corpus["examples"]
    assert examples, "Evaluation corpus contains no examples."

    top1_correct = 0
    top1_evaluable = 0
    top3_correct = 0
    top3_evaluable = 0
    no_match_correct = 0
    no_match_evaluable = 0
    candidate_set_sizes: list[int] = []

    failures: list[dict[str, Any]] = []

    for example in examples:
        request = example["request"]
        expected_id = example.get("expected_capability_id")
        acceptable_alternatives = list(example.get("acceptable_alternatives", []))
        category = example.get("category", "unknown")
        notes = example.get("notes", "")

        result: MatchResult = matcher.match(request, ContextRecord(), capabilities)
        top3_ids = [cap.id for cap in result.candidates[:3]]
        candidate_set_sizes.append(len(result.candidates))

        top1_ok = _is_correct_top(
            result.candidates[0].id if result.candidates else None,
            expected_id,
            acceptable_alternatives,
        )
        top3_ok = _is_correct_top3(top3_ids, expected_id, acceptable_alternatives)

        evaluable_for_top = expected_id is not None or bool(acceptable_alternatives)
        evaluable_for_no_match = expected_id is None and not acceptable_alternatives
        no_match_ok = evaluable_for_no_match and len(result.candidates) == 0

        if evaluable_for_top:
            top1_evaluable += 1
            top3_evaluable += 1
            if top1_ok:
                top1_correct += 1
            if top3_ok:
                top3_correct += 1

        if evaluable_for_no_match:
            no_match_evaluable += 1
            if no_match_ok:
                no_match_correct += 1

        if not (top1_ok if evaluable_for_top else no_match_ok if evaluable_for_no_match else True):
            failures.append({
                "request": request,
                "category": category,
                "expected_id": expected_id,
                "acceptable_alternatives": acceptable_alternatives,
                "top_candidate_id": result.candidates[0].id if result.candidates else None,
                "top_candidate_name": result.candidates[0].name if result.candidates else None,
                "top_score": result.confidence,
                "candidate_count": len(result.candidates),
                "candidate_ids": [cap.id for cap in result.candidates],
                "notes": notes,
            })

    top1_accuracy = (top1_correct / top1_evaluable) if top1_evaluable else 0.0
    top3_recall = (top3_correct / top3_evaluable) if top3_evaluable else 0.0
    no_match_precision = (no_match_correct / no_match_evaluable) if no_match_evaluable else 0.0
    avg_candidate_set_size = statistics.mean(candidate_set_sizes) if candidate_set_sizes else 0.0
    median_candidate_set_size = statistics.median(candidate_set_sizes) if candidate_set_sizes else 0.0

    print("\n=== RelevanceMatcher Evaluation Baseline ===")
    print(f"Corpus size        : {len(examples)} examples")
    print(f"Specific           : {sum(1 for e in examples if e.get('category') == 'specific')}")
    print(f"Generic            : {sum(1 for e in examples if e.get('category') == 'generic')}")
    print(f"Negative           : {sum(1 for e in examples if e.get('category') == 'negative')}")
    print(f"Ambiguous          : {sum(1 for e in examples if e.get('category') == 'ambiguous')}")
    print(f"Top-1 accuracy     : {top1_accuracy:.2%} ({top1_correct}/{top1_evaluable})")
    print(f"Top-3 recall       : {top3_recall:.2%} ({top3_correct}/{top3_evaluable})")
    print(f"No-match precision : {no_match_precision:.2%} ({no_match_correct}/{no_match_evaluable})")
    print(f"Avg candidate set  : {avg_candidate_set_size:.2f}")
    print(f"Median candidate set: {median_candidate_set_size:.1f}")

    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for failure in failures:
            print(
                f"  request={failure['request']!r:<30} "
                f"category={failure['category']:<10} "
                f"expected={failure['expected_id']!r:<30} "
                f"top={failure['top_candidate_id']!r:<30} "
                f"score={failure['top_score']:.3f} "
                f"count={failure['candidate_count']}"
            )
            if failure["notes"]:
                print(f"    notes: {failure['notes']}")
    else:
        print("\nAll examples passed.")

    assert len(examples) > 0
    capability_ids = {cap.id for cap in capabilities}
    for example in examples:
        if example.get("expected_capability_id"):
            assert example["expected_capability_id"] in capability_ids
        for alt in example.get("acceptable_alternatives", []):
            assert alt in capability_ids
