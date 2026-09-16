import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Commitment, User
from app.schemas import CommitmentCreate, CommitmentOut, CommitmentUpdate

router = APIRouter(prefix="/v1/commitments", tags=["commitments"])


@router.get("", response_model=list[CommitmentOut])
async def list_commitments(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Commitment]:
    stmt = select(Commitment).where(Commitment.user_id == user.user_id)
    if status_filter:
        stmt = stmt.where(Commitment.status == status_filter)
    stmt = stmt.order_by(Commitment.due_at.asc().nulls_last())
    return list((await db.execute(stmt)).scalars())


@router.post("", response_model=CommitmentOut)
async def create_commitment(
    payload: CommitmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Commitment:
    commitment = Commitment(user_id=user.user_id, status="open", **payload.model_dump())
    db.add(commitment)
    await db.flush()
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="create",
        entity_type="commitment",
        entity_id=commitment.commitment_id,
        after={"title": commitment.title, "due_at": str(commitment.due_at)},
    )
    await db.commit()
    return commitment


@router.patch("/{commitment_id}", response_model=CommitmentOut)
async def update_commitment(
    commitment_id: uuid.UUID,
    payload: CommitmentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Commitment:
    result = await db.execute(
        select(Commitment).where(Commitment.commitment_id == commitment_id, Commitment.user_id == user.user_id)
    )
    commitment = result.scalar_one_or_none()
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    before = {"status": commitment.status, "due_at": str(commitment.due_at)}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(commitment, field, value)

    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="update",
        entity_type="commitment",
        entity_id=commitment.commitment_id,
        before=before,
        after={"status": commitment.status, "due_at": str(commitment.due_at)},
    )
    await db.commit()
    return commitment
