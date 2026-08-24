"""
Increment 21G/21J — RelevanceMatcher evaluation corpus.

Loads a labelled evaluation corpus and computes baseline metrics
against the existing RelevanceMatcher without changing production behaviour.

Metrics:
  - Top-1 accuracy
  - Top-3 recall
  - No-match precision
  - Average candidate-set size
  - Median candidate-set size
  - Score distributions by category
  - Score-gap distributions
  - Token coverage distributions
  - Match-source distributions

This file is measurement-only. It does not modify the matcher,
the action policy, contracts, or any production code.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from capability_matcher import MatchResult
from capabilities import Capability, CapabilityKind, CapabilityStatus
from enterprise_context import ContextRecord
from relevance_matcher import RelevanceMatcher


_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "evaluation_corpus.json"

_STOP_WORDS = RelevanceMatcher._STOP_WORDS


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


def _meaningful_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    filtered = [token for token in tokens if token not in _STOP_WORDS]
    return list(dict.fromkeys(filtered))


def _matched_tokens(meaningful: list[str], candidate: Capability) -> list[str]:
    name_tokens = set(re.findall(r"[a-z0-9]+", candidate.name.lower()))
    desc_tokens = set(re.findall(r"[a-z0-9]+", candidate.description.lower()))
    tag_tokens = set(re.findall(r"[a-z0-9]+", " ".join(candidate.tags).lower()))
    field_tokens = name_tokens | desc_tokens | tag_tokens
    return [token for token in meaningful if token in field_tokens]


def _match_sources(meaningful: list[str], candidate: Capability) -> dict[str, bool]:
    name_tokens = set(re.findall(r"[a-z0-9]+", candidate.name.lower()))
    desc_tokens = set(re.findall(r"[a-z0-9]+", candidate.description.lower()))
    tag_tokens = set(re.findall(r"[a-z0-9]+", " ".join(candidate.tags).lower()))
    matched = set(_matched_tokens(meaningful, candidate))
    return {
        "name": bool(matched & name_tokens),
        "description": bool(matched & desc_tokens),
        "tags": bool(matched & tag_tokens),
    }


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

    top_scores: list[float] = []
    second_scores: list[float] = []
    score_gaps: list[float] = []
    meaningful_token_counts: list[int] = []
    token_coverages: list[float] = []

    category_metrics: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "top1_correct": 0,
            "top1_evaluable": 0,
            "top3_correct": 0,
            "top3_evaluable": 0,
            "no_match_correct": 0,
            "no_match_evaluable": 0,
            "candidate_set_sizes": [],
            "top_scores": [],
            "score_gaps": [],
            "meaningful_token_counts": [],
            "token_coverages": [],
            "match_sources": {"name": 0, "description": 0, "tags": 0},
        }
    )

    failures: list[dict[str, Any]] = []

    for example in examples:
        request = example["request"]
        expected_id = example.get("expected_capability_id")
        acceptable_alternatives = list(example.get("acceptable_alternatives", []))
        category = example.get("category", "unknown")
        notes = example.get("notes", "")

        meaningful = _meaningful_tokens(request)
        result: MatchResult = matcher.match(request, ContextRecord(), capabilities)
        top3_ids = [cap.id for cap in result.candidates[:3]]
        candidate_set_sizes.append(len(result.candidates))

        top_candidate = result.candidates[0] if result.candidates else None
        top_score = result.confidence
        second_candidate = result.candidates[1] if len(result.candidates) > 1 else None
        second_score = result.candidate_confidences.get(second_candidate.id, 0.0) if second_candidate else 0.0
        score_gap = top_score - second_score if second_candidate else 0.0

        matched = _matched_tokens(meaningful, top_candidate) if top_candidate else []
        token_coverage = len(matched) / len(meaningful) if meaningful else 0.0
        sources = _match_sources(meaningful, top_candidate) if top_candidate else {}

        top1_ok = _is_correct_top(
            top_candidate.id if top_candidate else None,
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
                "top_candidate_id": top_candidate.id if top_candidate else None,
                "top_candidate_name": top_candidate.name if top_candidate else None,
                "top_score": top_score,
                "second_candidate_id": second_candidate.id if second_candidate else None,
                "second_score": second_score,
                "score_gap": score_gap,
                "candidate_count": len(result.candidates),
                "candidate_ids": [cap.id for cap in result.candidates],
                "meaningful_tokens": meaningful,
                "matched_tokens": matched,
                "token_coverage": token_coverage,
                "match_sources": sources,
                "notes": notes,
            })

        top_scores.append(top_score)
        if second_candidate:
            second_scores.append(second_score)
            score_gaps.append(score_gap)
        meaningful_token_counts.append(len(meaningful))
        token_coverages.append(token_coverage)

        cm = category_metrics[category]
        cm["count"] += 1
        if evaluable_for_top:
            cm["top1_evaluable"] += 1
            cm["top3_evaluable"] += 1
            if top1_ok:
                cm["top1_correct"] += 1
            if top3_ok:
                cm["top3_correct"] += 1
        if evaluable_for_no_match:
            cm["no_match_evaluable"] += 1
            if no_match_ok:
                cm["no_match_correct"] += 1
        cm["candidate_set_sizes"].append(len(result.candidates))
        cm["top_scores"].append(top_score)
        if second_candidate:
            cm["score_gaps"].append(score_gap)
        cm["meaningful_token_counts"].append(len(meaningful))
        cm["token_coverages"].append(token_coverage)
        for key, present in sources.items():
            if present:
                cm["match_sources"][key] += 1

    top1_accuracy = (top1_correct / top1_evaluable) if top1_evaluable else 0.0
    top3_recall = (top3_correct / top3_evaluable) if top3_evaluable else 0.0
    no_match_precision = (no_match_correct / no_match_evaluable) if no_match_evaluable else 0.0
    avg_candidate_set_size = statistics.mean(candidate_set_sizes) if candidate_set_sizes else 0.0
    median_candidate_set_size = statistics.median(candidate_set_sizes) if candidate_set_sizes else 0.0

    print("\n=== RelevanceMatcher Evaluation Baseline ===")
    print(f"Corpus size        : {len(examples)} examples")
    for cat in ["specific", "generic", "ambiguous", "negative"]:
        cm = category_metrics[cat]
        print(f"{cat.capitalize():<15}: {cm['count']} examples")
    print(f"Top-1 accuracy     : {top1_accuracy:.2%} ({top1_correct}/{top1_evaluable})")
    print(f"Top-3 recall       : {top3_recall:.2%} ({top3_correct}/{top3_evaluable})")
    print(f"No-match precision : {no_match_precision:.2%} ({no_match_correct}/{no_match_evaluable})")
    print(f"Avg candidate set  : {avg_candidate_set_size:.2f}")
    print(f"Median candidate set: {median_candidate_set_size:.1f}")

    print("\n--- Score distributions by category ---")
    for cat in ["specific", "generic", "ambiguous", "negative"]:
        cm = category_metrics[cat]
        scores = cm["top_scores"]
        if scores:
            print(
                f"  {cat:<10}: min={min(scores):.3f} max={max(scores):.3f} "
                f"mean={sum(scores)/len(scores):.3f} count={len(scores)}"
            )
        else:
            print(f"  {cat:<10}: no data")

    print("\n--- Score-gap distributions (multi-candidate) ---")
    for cat in ["specific", "generic", "ambiguous"]:
        cm = category_metrics[cat]
        gaps = cm["score_gaps"]
        if gaps:
            print(
                f"  {cat:<10}: min={min(gaps):.3f} max={max(gaps):.3f} "
                f"mean={sum(gaps)/len(gaps):.3f} count={len(gaps)}"
            )
        else:
            print(f"  {cat:<10}: no multi-candidate examples")

    print("\n--- Candidate-count distributions ---")
    for cat in ["specific", "generic", "ambiguous", "negative"]:
        cm = category_metrics[cat]
        sizes = cm["candidate_set_sizes"]
        avg = sum(sizes) / len(sizes) if sizes else 0.0
        print(f"  {cat:<10}: avg={avg:.2f} sizes={sizes}")

    print("\n--- Token coverage distributions ---")
    for cat in ["specific", "generic", "ambiguous"]:
        cm = category_metrics[cat]
        coverages = cm["token_coverages"]
        if coverages:
            print(
                f"  {cat:<10}: min={min(coverages):.2f} max={max(coverages):.2f} "
                f"mean={sum(coverages)/len(coverages):.2f}"
            )
        else:
            print(f"  {cat:<10}: no data")

    print("\n--- Match-source breakdown (top candidate) ---")
    for cat in ["specific", "generic", "ambiguous"]:
        cm = category_metrics[cat]
        total = sum(cm["match_sources"].values())
        if total:
            parts = [f"{k}={v}" for k, v in sorted(cm["match_sources"].items())]
            print(f"  {cat:<10}: {' '.join(parts)}")
        else:
            print(f"  {cat:<10}: no data")

    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for failure in failures:
            print(
                f"  request={failure['request']!r:<40} "
                f"category={failure['category']:<10} "
                f"expected={failure['expected_id']!r:<30} "
                f"top={failure['top_candidate_name']!r:<25} "
                f"score={failure['top_score']:.3f} "
                f"gap={failure['score_gap']:.3f} "
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
