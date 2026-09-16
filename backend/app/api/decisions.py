import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Decision, User
from app.schemas import DecisionCreate, DecisionOut

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


class DecisionReviewIn(BaseModel):
    outcome_notes: str
    status: str = "reviewed"


@router.get("", response_model=list[DecisionOut])
async def list_decisions(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Decision]:
    stmt = select(Decision).where(Decision.user_id == user.user_id)
    if status_filter:
        stmt = stmt.where(Decision.status == status_filter)
    stmt = stmt.order_by(Decision.created_at.desc())
    return list((await db.execute(stmt)).scalars())


@router.post("", response_model=DecisionOut)
async def create_decision(
    payload: DecisionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Decision:
    status_ = "decided" if payload.selected_option else "open"
    decision = Decision(user_id=user.user_id, status=status_, **payload.model_dump())
    db.add(decision)
    await db.flush()
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="create",
        entity_type="decision",
        entity_id=decision.decision_id,
        after={"question": decision.question, "status": decision.status},
    )
    await db.commit()
    return decision


@router.patch("/{decision_id}/review", response_model=DecisionOut)
async def review_decision(
    decision_id: uuid.UUID,
    payload: DecisionReviewIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Decision:
    """Closes the decision-journal learning loop (document §11 'Learning' engine, §28 DoD:
    compare predicted vs. actual outcome)."""
    result = await db.execute(
        select(Decision).where(Decision.decision_id == decision_id, Decision.user_id == user.user_id)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    before = {"status": decision.status}
    decision.status = payload.status
    decision.rationale = (decision.rationale or "") + f"\n[review] {payload.outcome_notes}"
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="review",
        entity_type="decision",
        entity_id=decision.decision_id,
        before=before,
        after={"status": decision.status},
    )
    await db.commit()
    return decision
