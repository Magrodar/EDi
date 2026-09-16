"""Intervention scoring and alert creation with cooldown/dedup (document §12.1-12.3).

`compute_intervention_score` and `alert_level_for_score` are pure and unit-tested directly
against the document's formula and thresholds. `create_alert` adds the DB-side dedup rule:
don't repeat an unchanged alert within the cooldown window; do escalate immediately when the
computed level rises.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Alert

_LEVEL_ORDER = ["info", "advisory", "warning", "command_alert"]
_LEVEL_STATUS = {
    "info": "brief_queue",
    "advisory": "advisory_sent",
    "warning": "warning_sent",
    "command_alert": "command_alert_sent",
}


def compute_intervention_score(
    *,
    impact: float,
    urgency: float,
    cost_of_delay: float,
    irreversibility: float,
    dependency_centrality: float,
    strategic_alignment: float,
    confidence: float,
    attention_cost: float = 0.0,
) -> float:
    score = (
        impact * 0.30
        + urgency * 0.20
        + cost_of_delay * 0.15
        + irreversibility * 0.10
        + dependency_centrality * 0.10
        + strategic_alignment * 0.10
        + confidence * 0.05
        - attention_cost
    )
    return round(max(0.0, min(1.0, score)), 3)


def alert_level_for_score(score: float, *, red_line: bool = False) -> str | None:
    if red_line or score > 0.90:
        return "command_alert"
    if score >= 0.75:
        return "warning"
    if score >= 0.60:
        return "advisory"
    if score >= 0.45:
        return "info"
    return None  # silent/store — no alert row


async def create_alert(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    dedup_key: str,
    score: float,
    reason: str,
    evidence: list,
    recommended_action: str | None,
    related_type: str | None,
    related_id: uuid.UUID | None,
    red_line: bool = False,
) -> Alert | None:
    level = alert_level_for_score(score, red_line=red_line)
    if level is None:
        return None

    existing_q = await db.execute(
        select(Alert)
        .where(Alert.user_id == user_id, Alert.dedup_key == dedup_key)
        .order_by(Alert.created_at.desc())
        .limit(1)
    )
    existing = existing_q.scalar_one_or_none()

    if existing is not None:
        cooldown = timedelta(minutes=settings.edi_alert_cooldown_minutes)
        unchanged = _LEVEL_ORDER.index(level) <= _LEVEL_ORDER.index(existing.level)
        created_at = existing.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        within_cooldown = datetime.now(timezone.utc) - created_at < cooldown
        if unchanged and within_cooldown and existing.status not in ("resolved",):
            return None  # suppressed: unchanged severity within cooldown (§12.3)

    alert = Alert(
        user_id=user_id,
        level=level,
        reason=reason,
        evidence=evidence,
        recommended_action=recommended_action,
        related_type=related_type,
        related_id=related_id,
        dedup_key=dedup_key,
        intervention_score=score,
        status=_LEVEL_STATUS[level],
    )
    db.add(alert)
    await db.flush()
    return alert
