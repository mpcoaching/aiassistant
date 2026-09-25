"""
Relevance matcher (Increment 21B, 21H).

Deterministic keyword-based capability matcher. Replaces HumanSelectionMatcher
with a matcher that scores candidates by keyword relevance to the request text
and returns ranked results with confidence scores.

Matching belongs to People/Capability. This implementation is pure,
side-effect free, and independent of external services.
"""

from __future__ import annotations

import re

from capability import Capability, CapabilityStatus
from capability_matcher import CapabilityMatcher, MatchResult
from enterprise_context import ContextRecord
from pydantic import BaseModel


_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "as",
        "by",
        "at",
        "from",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
    }
)

_STOP_WORDS_RATIONALE = """
Stop words are functional English words that carry little semantic content
for capability matching. They are removed only from the request/query side,
not from capability metadata. The set is intentionally small and conservative:

- Articles: a, an, the
- Auxiliary verbs: is, are, was, were, be, been, being, have, has, had,
  do, does, did, will, would, could, should, may, might, must, shall, can
- Common prepositions/conjunctions: to, of, in, for, on, with, as, by, at,
  from, through, during, before, after, above, below, between, out, off,
  over, under, again, further, then, once

Words that could legitimately appear in capability names, descriptions, or
tags (nouns, content verbs, adjectives) are deliberately excluded. For
example, "create", "send", "analyse", "data", "email", "report", "lead",
"artifact", "test", "notification", "generate" are NOT stop words.
"""


class RelevanceMatcher:
    """Deterministic keyword-based capability matcher.

    Scores capabilities by keyword overlap between the request text and
    the capability's name, description, and tags. Returns ranked candidates
    with a confidence score representing the highest relevance found.

    Request tokens are normalised by removing a small, explicit stop-word set
    and deduplicating repeated terms before scoring. Capability metadata is
    not normalised.
    """

    matcher_id = "relevance"
    _STOP_WORDS = _STOP_WORDS

    def match(
        self,
        request_text: str,
        context: ContextRecord,
        capabilities: list[Capability],
    ) -> MatchResult:
        request_tokens = self._tokenise(request_text)
        if not request_tokens:
            return MatchResult(
                candidates=[],
                confidence=0.0,
                matcher_id=self.matcher_id,
                rationale="No tokens to match",
            )

        scored: list[tuple[float, str, Capability]] = []

        for capability in capabilities:
            if capability.status == CapabilityStatus.DEPRECATED:
                continue

            name_tokens = self._tokenise(capability.name)
            description_tokens = self._tokenise(capability.description)
            tag_tokens = self._tokenise(" ".join(capability.tags))

            name_score = self._overlap(request_tokens, name_tokens)
            description_score = self._overlap(request_tokens, description_tokens)
            tag_score = self._overlap(request_tokens, tag_tokens)

            combined = name_score * 0.5 + description_score * 0.3 + tag_score * 0.2

            if combined > 0.0:
                scored.append((combined, capability.name, capability))

        scored.sort(key=lambda x: (-x[0], x[1]))

        candidates = [cap for _, _, cap in scored]
        confidence = scored[0][0] if scored else 0.0
        candidate_confidences = {cap.id: score for score, _, cap in scored}

        return MatchResult(
            candidates=candidates,
            confidence=confidence,
            matcher_id=self.matcher_id,
            candidate_confidences=candidate_confidences,
            rationale=f"Matched {len(candidates)} capabilities by keyword relevance",
        )

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9]+", lowered)
        filtered = [token for token in tokens if token not in RelevanceMatcher._STOP_WORDS]
        return list(dict.fromkeys(filtered))

    @staticmethod
    def _overlap(request_tokens: list[str], field_tokens: list[str]) -> float:
        if not request_tokens:
            return 0.0
        field_set = set(field_tokens)
        matches = sum(1 for token in request_tokens if token in field_set)
        return matches / len(request_tokens)
