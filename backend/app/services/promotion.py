"""Memory promotion engine (document §9.2/§9.3, §34.1).

`compute_promotion_score` is a pure function so it can be unit-tested against the document's
formula directly. `promote_fact` wraps it with the DB side: conflict detection against an
existing canonical/provisional fact for the same (subject_label, predicate), and the rule
that restricted-sensitivity facts never auto-promote regardless of score.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ExtractedFact
from app.models import Fact

PROMOTION_THRESHOLD = 0.65

_WEIGHTS = {
    "strategic_relevance": 0.25,
    "future_reuse_probability": 0.20,
    "commitment_or_deadline_weight": 0.20,
    "risk_or_opportunity_weight": 0.15,
    "repetition_signal": 0.10,
    "user_explicitness": 0.10,
}

_DURABLE_SUBJECT_TYPES = {"project", "person", "material", "forecast", "supplier"}


def compute_promotion_score(
    *,
    strategic_relevance: float,
    future_reuse_probability: float,
    commitment_or_deadline_weight: float,
    risk_or_opportunity_weight: float,
    repetition_signal: float,
    user_explicitness: float,
) -> float:
    signals = {
        "strategic_relevance": strategic_relevance,
        "future_reuse_probability": future_reuse_probability,
        "commitment_or_deadline_weight": commitment_or_deadline_weight,
        "risk_or_opportunity_weight": risk_or_opportunity_weight,
        "repetition_signal": repetition_signal,
        "user_explicitness": user_explicitness,
    }
    for name, value in signals.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1], got {value}")
    return round(sum(_WEIGHTS[name] * value for name, value in signals.items()), 3)


def score_extracted_fact(
    fact: ExtractedFact,
    *,
    project_linked: bool,
    explicit_flag: bool,
    repetition_count: int,
    linked_to_risk_or_opportunity: bool,
) -> float:
    return compute_promotion_score(
        strategic_relevance=1.0 if project_linked else 0.4,
        future_reuse_probability=0.8 if fact.subject_type in _DURABLE_SUBJECT_TYPES else 0.5,
        commitment_or_deadline_weight=1.0 if fact.effective_from else 0.3,
        risk_or_opportunity_weight=1.0 if linked_to_risk_or_opportunity else 0.2,
        repetition_signal=min(1.0, repetition_count / 3),
        user_explicitness=1.0 if explicit_flag else 0.3,
    )


@dataclass
class PromotionOutcome:
    fact: Fact
    contradiction_with: uuid.UUID | None = None


async def promote_fact(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    extracted: ExtractedFact,
    source_event_id: uuid.UUID | None,
    sensitivity: str,
    project_linked: bool,
    explicit_flag: bool = False,
    linked_to_risk_or_opportunity: bool = False,
) -> PromotionOutcome:
    existing_q = await db.execute(
        select(Fact).where(
            Fact.user_id == user_id,
            Fact.subject_label.ilike(extracted.subject_label),
            Fact.predicate == extracted.predicate,
            Fact.status.in_(["canonical", "provisional"]),
            Fact.deleted_at.is_(None),
        )
    )
    existing_facts = list(existing_q.scalars())
    repetition_count = sum(1 for f in existing_facts if f.value_json == extracted.value)

    score = score_extracted_fact(
        extracted,
        project_linked=project_linked,
        explicit_flag=explicit_flag,
        repetition_count=repetition_count,
        linked_to_risk_or_opportunity=linked_to_risk_or_opportunity,
    )

    if sensitivity == "restricted":
        status = "provisional"  # never auto-canonical regardless of score (§9.2)
    else:
        status = "canonical" if score >= PROMOTION_THRESHOLD else "provisional"

    contradiction_with = None
    conflicting = [f for f in existing_facts if f.value_json != extracted.value]
    if conflicting:
        # §34.1 rule 5: if high-confidence sources conflict materially, keep the conflict
        # open rather than silently merging.
        strongest = max(conflicting, key=lambda f: float(f.confidence))
        if strongest.status == "canonical" and status == "canonical":
            strongest.status = "conflicted"
            status = "conflicted"
            contradiction_with = strongest.fact_id
        elif strongest.status == "provisional" and extracted.confidence >= float(strongest.confidence):
            strongest.status = "superseded"
            # superseded_by is backfilled once the new fact has an id (see below).

    new_fact = Fact(
        user_id=user_id,
        subject_type=extracted.subject_type,
        subject_label=extracted.subject_label,
        predicate=extracted.predicate,
        value_json=extracted.value if isinstance(extracted.value, (dict, list)) else {"value": extracted.value},
        effective_from=extracted.effective_from,
        confidence=extracted.confidence,
        status=status,
        sensitivity=sensitivity,
        promotion_score=score,
        source_event_id=source_event_id,
    )
    db.add(new_fact)
    await db.flush()  # assign fact_id

    for f in conflicting:
        if f.status == "superseded" and f.superseded_by is None:
            f.superseded_by = new_fact.fact_id

    return PromotionOutcome(fact=new_fact, contradiction_with=contradiction_with)
