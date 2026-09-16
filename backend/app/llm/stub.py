"""Deterministic heuristic extractor. No API key, no network call.

Good enough to exercise the full event -> extraction -> promotion pipeline in dev/tests.
It is intentionally conservative: everything it emits gets confidence <= 0.65, which keeps
it below the document's 0.65 durable-memory threshold on its own (see
app/services/promotion.py) unless corroborated — matching §9.2's rule that uncertain facts
should stay provisional rather than become canonical.
"""

import re
from datetime import datetime, timedelta, timezone

from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta

from app.llm.base import (
    ExtractedCommitment,
    ExtractedDecision,
    ExtractedFact,
    ExtractedRisk,
    ExtractionProvider,
    ExtractionResult,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

_COMMITMENT_CUES = re.compile(r"\bi(?:'ll| will)\b|\bneed to\b|\bmust\b|\bpromise(?:d)?\b|\bwill\s+\w+\s+by\b", re.I)
_RISK_CUES = re.compile(
    r"\brisk\b|\bmay (?:delay|miss|slip)\b|\bmight (?:delay|miss|slip)\b|\bcould (?:delay|miss)\b|"
    r"\bshortage\b|\bbehind schedule\b|\bjeopardiz|\bconcern(?:ed)?\b",
    re.I,
)
_DECISION_CUES = re.compile(r"\bdecided to\b|\bwe(?:'ll| will) go with\b|\bchose to\b|\bdecision:\s*", re.I)
_FACT_CUE = re.compile(
    r"(?P<subject>.+?)\s+(?:expects?|expected)\s+(?P<value>.+?)\s+(?:on|by)\s+(?P<date>.+)", re.I
)
_DATE_HINT = re.compile(
    r"\b(?:on |by )?(?:\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+\w+|\w+\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"tomorrow|today|next week|next month|the \d{1,2}(?:st|nd|rd|th)?)\b",
    re.I,
)


_RELATIVE_TERMS = {"today": timedelta(days=0), "tomorrow": timedelta(days=1), "next week": timedelta(weeks=1)}


def _find_date(text: str, *, default: datetime | None) -> datetime | None:
    match = _DATE_HINT.search(text)
    if not match:
        return None

    base = default or datetime.now(timezone.utc)
    raw = match.group(0).strip().lower()
    for prefix in ("on ", "by "):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break

    # dateutil's parser only understands absolute date formats, not relative terms like
    # "tomorrow" -- handle those explicitly before falling back to it.
    if raw in _RELATIVE_TERMS:
        return base + _RELATIVE_TERMS[raw]
    if raw == "next month":
        return base + relativedelta(months=1)

    try:
        return dateparser.parse(match.group(0), fuzzy=True, default=base)
    except (ValueError, OverflowError):
        return None


def _severity_bump(sentence: str) -> float:
    if re.search(r"\bcritical\b|\bsevere\b|\bmajor\b", sentence, re.I):
        return 0.25
    return 0.0


class StubExtractionProvider(ExtractionProvider):
    async def extract(self, text: str, *, occurred_at: datetime | None = None) -> ExtractionResult:
        result = ExtractionResult()
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]

        for sentence in sentences:
            if _DECISION_CUES.search(sentence):
                result.decisions.append(
                    ExtractedDecision(question=sentence, selected_option=None, source_span=sentence)
                )
                continue  # a decision sentence is not also treated as a bare commitment

            if _COMMITMENT_CUES.search(sentence):
                result.commitments.append(
                    ExtractedCommitment(
                        title=sentence,
                        due_at=_find_date(sentence, default=occurred_at),
                        confidence=0.55,
                        source_span=sentence,
                    )
                )

            if _RISK_CUES.search(sentence):
                impact = min(0.9, 0.5 + _severity_bump(sentence))
                result.risks.append(
                    ExtractedRisk(
                        title=sentence,
                        probability=0.5,
                        impact=impact,
                        needs_review=True,
                        source_span=sentence,
                    )
                )

            fact_match = _FACT_CUE.match(sentence)
            if fact_match:
                when = _find_date(fact_match.group("date"), default=occurred_at)
                result.facts.append(
                    ExtractedFact(
                        subject_type="unresolved",
                        subject_label=fact_match.group("subject").strip(),
                        predicate="expected_value",
                        value=fact_match.group("value").strip(),
                        confidence=0.6,
                        effective_from=when,
                        source_span=sentence,
                    )
                )

        return result
