"""Pluggable extraction-provider contract.

The document is explicit (§18) that the model may only *propose* facts — a validator
decides what becomes canonical — and (§37.1) that untrusted content is never concatenated
with instructions as a peer. Both rules live outside this interface: the caller
(app/services/extraction.py) wraps `text` as evidence before calling `extract()`, and
app/services/promotion.py is the only place that can mark a fact canonical.

Swap providers via EDI_LLM_PROVIDER — no call site outside app/llm/__init__.py changes.
"""

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class ExtractedFact(BaseModel):
    subject_type: str
    subject_label: str
    predicate: str
    value: Any
    confidence: float
    effective_from: datetime | None = None
    source_span: str | None = None


class ExtractedCommitment(BaseModel):
    title: str
    owner_hint: str | None = None
    due_at: datetime | None = None
    confidence: float
    source_span: str | None = None


class ExtractedRisk(BaseModel):
    title: str
    probability: float
    impact: float
    needs_review: bool = False
    source_span: str | None = None


class ExtractedDecision(BaseModel):
    question: str
    selected_option: str | None = None
    source_span: str | None = None


class ExtractionResult(BaseModel):
    facts: list[ExtractedFact] = Field(default_factory=list)
    commitments: list[ExtractedCommitment] = Field(default_factory=list)
    risks: list[ExtractedRisk] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)


class ExtractionProvider(Protocol):
    async def extract(self, text: str, *, occurred_at: datetime | None = None) -> ExtractionResult: ...
