"""Deterministic 'what am I missing?' scan (document §14.1's manual scan, Phase 1 scope).

This is intentionally simple — overdue/near-due commitments, high-exposure open risks, and
decisions overdue for review — not the full contradiction/dependency/pattern/opportunity
engine set from §11 (that's Phase 3). It reuses the same intervention_score formula and
alert dedup/cooldown as everything else in app/services/alerts.py, so results compose
naturally with the daily brief and the alerts API.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Commitment, Decision, Risk
from app.services import alerts as alerts_service


def _urgency_from_due(due_at: datetime | None, now: datetime) -> float:
    if due_at is None:
        return 0.1
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    delta_hours = (due_at - now).total_seconds() / 3600
    if delta_hours < 0:
        return 1.0
    if delta_hours <= 24:
        return 0.9
    if delta_hours <= 72:
        return 0.6
    if delta_hours <= 168:
        return 0.4
    return 0.2


async def _scan_commitments(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Alert]:
    q = await db.execute(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.status.in_(["open", "in_progress", "blocked"]),
            Commitment.due_at.is_not(None),
        )
    )
    created: list[Alert] = []
    for c in q.scalars():
        urgency = _urgency_from_due(c.due_at, now)
        if urgency < 0.4:
            continue  # not due soon enough to be worth surfacing outside the brief
        impact = 0.6 if c.priority is None else max(0.3, 1 - (c.priority - 1) * 0.2)
        cost_of_delay = min(1.0, float(c.cost_of_delay) / 10) if c.cost_of_delay else urgency * 0.5
        score = alerts_service.compute_intervention_score(
            impact=impact,
            urgency=urgency,
            cost_of_delay=cost_of_delay,
            irreversibility=0.2,
            dependency_centrality=min(1.0, len(c.dependency_ids) / 3),
            strategic_alignment=0.7 if c.project_id else 0.4,
            confidence=0.7,
        )
        overdue = c.due_at.replace(tzinfo=timezone.utc) < now if c.due_at.tzinfo is None else c.due_at < now
        alert = await alerts_service.create_alert(
            db,
            user_id=user_id,
            dedup_key=f"commitment_due:{c.commitment_id}",
            score=score,
            reason=f"Commitment '{c.title}' is {'overdue' if overdue else 'due soon'} ({c.due_at}).",
            evidence=[{"commitment_id": str(c.commitment_id)}],
            recommended_action="Confirm status, reschedule, or close it out.",
            related_type="commitment",
            related_id=c.commitment_id,
        )
        if alert is not None:
            created.append(alert)
    return created


async def _scan_risks(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Alert]:
    q = await db.execute(select(Risk).where(Risk.user_id == user_id, Risk.status == "open"))
    created: list[Alert] = []
    for r in q.scalars():
        if r.exposure is None or float(r.exposure) < 0.3:
            continue
        score = alerts_service.compute_intervention_score(
            impact=float(r.impact or 0.5),
            urgency=0.7,
            cost_of_delay=float(r.exposure),
            irreversibility=0.4,
            dependency_centrality=0.4,
            strategic_alignment=0.7 if r.project_id else 0.4,
            confidence=float(r.probability or 0.5),
        )
        alert = await alerts_service.create_alert(
            db,
            user_id=user_id,
            dedup_key=f"risk_exposure:{r.risk_id}",
            score=score,
            reason=f"Risk '{r.title}' has exposure {r.exposure} and is still open.",
            evidence=[{"risk_id": str(r.risk_id)}],
            recommended_action="Confirm mitigation owner and next check-in date.",
            related_type="risk",
            related_id=r.risk_id,
        )
        if alert is not None:
            created.append(alert)
    return created


async def _scan_decisions(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Alert]:
    q = await db.execute(
        select(Decision).where(
            Decision.user_id == user_id,
            Decision.status == "decided",
            Decision.review_at.is_not(None),
            Decision.review_at < now,
        )
    )
    created: list[Alert] = []
    for d in q.scalars():
        score = alerts_service.compute_intervention_score(
            impact=0.3, urgency=0.5, cost_of_delay=0.2, irreversibility=0.2,
            dependency_centrality=0.1, strategic_alignment=0.4, confidence=0.6,
        )
        alert = await alerts_service.create_alert(
            db,
            user_id=user_id,
            dedup_key=f"decision_review:{d.decision_id}",
            score=score,
            reason=f"Decision '{d.question}' is due for outcome review.",
            evidence=[{"decision_id": str(d.decision_id)}],
            recommended_action="Compare predicted vs. actual outcome; close the learning loop.",
            related_type="decision",
            related_id=d.decision_id,
        )
        if alert is not None:
            created.append(alert)
    return created


async def run_missing_scan(db: AsyncSession, user_id: uuid.UUID) -> list[Alert]:
    now = datetime.now(timezone.utc)
    alerts: list[Alert] = []
    alerts += await _scan_commitments(db, user_id, now)
    alerts += await _scan_risks(db, user_id, now)
    alerts += await _scan_decisions(db, user_id, now)
    return alerts
