import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Fact, User
from app.schemas import FactOut
from app.services.search import search_memory

router = APIRouter(prefix="/v1/memory", tags=["memory"])


class PromoteIn(BaseModel):
    fact_id: uuid.UUID


@router.post("/promote", response_model=FactOut)
async def promote_memory(
    payload: PromoteIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Fact:
    """Explicit user override: force a provisional fact to canonical (document §9.3 — Mahmoud
    can inspect, correct, archive and delete memory)."""
    result = await db.execute(
        select(Fact).where(Fact.fact_id == payload.fact_id, Fact.user_id == user.user_id)
    )
    fact = result.scalar_one_or_none()
    if fact is None or fact.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Fact not found")

    before = {"status": fact.status}
    fact.status = "canonical"
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="promote",
        entity_type="fact",
        entity_id=fact.fact_id,
        before=before,
        after={"status": fact.status},
    )
    await db.commit()
    return fact


@router.get("/search", response_model=list[FactOut])
async def search(
    q: str = "",
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Fact]:
    return await search_memory(db, user_id=user.user_id, query=q, limit=limit)


@router.delete("/{fact_id}")
async def delete_memory(
    fact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft delete: removed from retrieval immediately, audit metadata preserved
    (document §20.2 deletion test, §42 retention defaults)."""
    result = await db.execute(select(Fact).where(Fact.fact_id == fact_id, Fact.user_id == user.user_id))
    fact = result.scalar_one_or_none()
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")

    fact.deleted_at = datetime.now(timezone.utc)
    fact.status = "deleted"
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="delete",
        entity_type="fact",
        entity_id=fact.fact_id,
        before={"status": "deleted_at_null"},
        after={"deleted_at": fact.deleted_at.isoformat()},
    )
    await db.commit()
    return {"deleted": True, "fact_id": str(fact_id)}
