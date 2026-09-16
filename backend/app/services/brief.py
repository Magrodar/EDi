"""Deterministic Daily Commander Brief (document §14.1's rule table). No model call — this
is exactly the kind of thing §26 says not to spend tokens on: deterministic code answers it.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Commitment, Decision, Risk


def _commitment_dict(c: Commitment) -> dict:
    return {
        "commitment_id": str(c.commitment_id),
        "title": c.title,
        "due_at": c.due_at.isoformat() if c.due_at else None,
        "status": c.status,
        "owner_person_id": str(c.owner_person_id) if c.owner_person_id else None,
    }


def _risk_dict(r: Risk) -> dict:
    return {
        "risk_id": str(r.risk_id),
        "title": r.title,
        "exposure": float(r.exposure) if r.exposure is not None else None,
        "status": r.status,
    }


def _decision_dict(d: Decision) -> dict:
    return {"decision_id": str(d.decision_id), "question": d.question, "status": d.status}


async def build_daily_brief(db: AsyncSession, user_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=7)

    commitments_q = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.status.in_(["open", "in_progress", "blocked"]),
            Commitment.due_at.is_not(None),
            Commitment.due_at <= soon,
        )
        .order_by(Commitment.due_at.asc())
    )
    due_soon = list(commitments_q.scalars())

    risks_q = await db.execute(
        select(Risk)
        .where(Risk.user_id == user_id, Risk.status == "open")
        .order_by(Risk.exposure.desc().nulls_last())
    )
    open_risks = list(risks_q.scalars())
    action_relevant_risks = [r for r in open_risks if r.exposure is not None and float(r.exposure) >= 0.3]

    decisions_q = await db.execute(
        select(Decision).where(Decision.user_id == user_id, Decision.status == "open")
    )
    open_decisions = list(decisions_q.scalars())

    waiting_on = [c for c in due_soon if c.owner_person_id is not None]

    command_alert_q = await db.execute(
        select(Alert)
        .where(Alert.user_id == user_id, Alert.level == "command_alert", Alert.status != "resolved")
        .order_by(Alert.created_at.desc())
        .limit(1)
    )
    command_alert = command_alert_q.scalar_one_or_none()

    priority_1 = None
    if command_alert is not None:
        priority_1 = {"type": "alert", "reason": command_alert.reason, "alert_id": str(command_alert.alert_id)}
    elif due_soon:
        priority_1 = {"type": "commitment", **_commitment_dict(due_soon[0])}
    elif action_relevant_risks:
        priority_1 = {"type": "risk", **_risk_dict(action_relevant_risks[0])}

    critical_tasks = [_commitment_dict(c) for c in due_soon[:3]]
    decisions_needed = [_decision_dict(d) for d in open_decisions[:5]]
    risks_changed = [_risk_dict(r) for r in action_relevant_risks[:5]]
    waiting_on_out = [_commitment_dict(c) for c in waiting_on[:5]]
    commitments_due_soon = [_commitment_dict(c) for c in due_soon[:10]]

    if priority_1:
        target = priority_1.get("title") or priority_1.get("reason") or "your top item"
        deep_work_recommendation = f"Protect one focused block for: {target}"
    else:
        deep_work_recommendation = "No pressing deadline detected — protect a block for strategic/deep work."

    overdue_count = sum(1 for c in due_soon if c.due_at and c.due_at.replace(tzinfo=timezone.utc) < now)
    unmitigated_risks = [r for r in action_relevant_risks if not r.mitigation_json]
    if overdue_count >= 2:
        edi_observation = f"{overdue_count} commitments are overdue — check whether this is one blocker or a pattern."
    elif len(unmitigated_risks) >= 2:
        edi_observation = f"{len(unmitigated_risks)} open risks have no recorded mitigation owner or plan."
    else:
        edi_observation = None

    return {
        "generated_at": now,
        "priority_1": priority_1,
        "critical_tasks": critical_tasks,
        "decisions_needed": decisions_needed,
        "risks_changed": risks_changed,
        "waiting_on": waiting_on_out,
        "commitments_due_soon": commitments_due_soon,
        "deep_work_recommendation": deep_work_recommendation,
        "edi_observation": edi_observation,
    }
