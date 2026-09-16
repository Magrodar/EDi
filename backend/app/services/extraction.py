"""Orchestrates: raw text -> extraction provider -> validated candidates -> persisted
Facts/Commitments/Risks/Decisions -> contradiction alerts. This is the only place that turns
model output into rows in the source-of-truth tables (document §18: models propose, validators
decide).
"""

import re
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ExtractionResult
from app.models import Commitment, Decision, Event, Risk
from app.services import alerts as alerts_service
from app.services.embeddings import get_embedding_provider
from app.services.promotion import promote_fact

_EXPLICIT_MEMORY_CUE = re.compile(r"\bremember this\b", re.I)


async def persist_extraction(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event: Event,
    result: ExtractionResult,
) -> dict:
    project_linked = bool(event.project_ids)
    explicit_flag = bool(_EXPLICIT_MEMORY_CUE.search(event.normalized_text or ""))
    risk_subjects = [r.title.lower() for r in result.risks]
    embedding_provider = get_embedding_provider()

    persisted_facts = []
    alerts_created = 0

    for extracted_fact in result.facts:
        linked_to_risk = any(extracted_fact.subject_label.lower() in title for title in risk_subjects)
        outcome = await promote_fact(
            db,
            user_id=user_id,
            extracted=extracted_fact,
            source_event_id=event.event_id,
            sensitivity=event.sensitivity,
            project_linked=project_linked,
            explicit_flag=explicit_flag,
            linked_to_risk_or_opportunity=linked_to_risk,
        )
        persisted_facts.append(outcome.fact)

        embedding_text = f"{extracted_fact.subject_label} {extracted_fact.predicate} {extracted_fact.value}"
        outcome.fact.embedding = await embedding_provider.embed(embedding_text)

        if outcome.contradiction_with is not None:
            score = alerts_service.compute_intervention_score(
                impact=0.7,
                urgency=0.6,
                cost_of_delay=0.5,
                irreversibility=0.3,
                dependency_centrality=0.5,
                strategic_alignment=0.6,
                confidence=extracted_fact.confidence,
            )
            created = await alerts_service.create_alert(
                db,
                user_id=user_id,
                dedup_key=f"contradiction:{extracted_fact.subject_label.lower()}:{extracted_fact.predicate}",
                score=score,
                reason=(
                    f"New information conflicts with an existing fact about "
                    f"'{extracted_fact.subject_label}' ({extracted_fact.predicate})."
                ),
                evidence=[
                    {"fact_id": str(outcome.fact.fact_id)},
                    {"conflicts_with_fact_id": str(outcome.contradiction_with)},
                    {"source_event_id": str(event.event_id)},
                ],
                recommended_action="Review both facts and resolve which is current.",
                related_type="fact",
                related_id=outcome.fact.fact_id,
            )
            if created is not None:
                alerts_created += 1

    persisted_commitments = []
    for c in result.commitments:
        commitment = Commitment(
            user_id=user_id,
            project_id=event.project_ids[0] if event.project_ids else None,
            title=c.title,
            due_at=c.due_at,
            status="open",
            priority=3,
            source_event_id=event.event_id,
        )
        db.add(commitment)
        persisted_commitments.append(commitment)

    persisted_risks = []
    for r in result.risks:
        exposure = round(r.probability * r.impact, 3)
        risk = Risk(
            user_id=user_id,
            project_id=event.project_ids[0] if event.project_ids else None,
            title=r.title,
            probability=r.probability,
            impact=r.impact,
            exposure=exposure,
            status="open",
            source_event_id=event.event_id,
        )
        db.add(risk)
        persisted_risks.append(risk)

    for d in result.decisions:
        db.add(
            Decision(
                user_id=user_id,
                project_id=event.project_ids[0] if event.project_ids else None,
                question=d.question,
                selected_option={"value": d.selected_option} if d.selected_option else None,
                status="decided" if d.selected_option else "open",
                source_event_id=event.event_id,
            )
        )

    await db.flush()

    return {
        "facts": persisted_facts,
        "commitments": persisted_commitments,
        "risks": persisted_risks,
        "alerts_created": alerts_created,
    }
