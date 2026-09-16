import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Risk, User
from app.schemas import RiskCreate, RiskOut, RiskUpdate

router = APIRouter(prefix="/v1/risks", tags=["risks"])


@router.get("", response_model=list[RiskOut])
async def list_risks(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Risk]:
    stmt = select(Risk).where(Risk.user_id == user.user_id)
    if status_filter:
        stmt = stmt.where(Risk.status == status_filter)
    stmt = stmt.order_by(Risk.exposure.desc().nulls_last())
    return list((await db.execute(stmt)).scalars())


@router.post("", response_model=RiskOut)
async def create_risk(
    payload: RiskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Risk:
    data = payload.model_dump()
    probability = data.pop("probability") or 0.5
    impact = data.pop("impact") or 0.5
    risk = Risk(
        user_id=user.user_id,
        status="open",
        probability=probability,
        impact=impact,
        exposure=round(probability * impact, 3),
        **data,
    )
    db.add(risk)
    await db.flush()
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="create",
        entity_type="risk",
        entity_id=risk.risk_id,
        after={"title": risk.title, "exposure": str(risk.exposure)},
    )
    await db.commit()
    return risk


@router.patch("/{risk_id}", response_model=RiskOut)
async def update_risk(
    risk_id: uuid.UUID,
    payload: RiskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Risk:
    result = await db.execute(select(Risk).where(Risk.risk_id == risk_id, Risk.user_id == user.user_id))
    risk = result.scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")

    before = {"status": risk.status, "exposure": str(risk.exposure)}
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(risk, field, value)
    if "probability" in updates or "impact" in updates:
        risk.exposure = round(float(risk.probability or 0) * float(risk.impact or 0), 3)

    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="update",
        entity_type="risk",
        entity_id=risk.risk_id,
        before=before,
        after={"status": risk.status, "exposure": str(risk.exposure)},
    )
    await db.commit()
    return risk
