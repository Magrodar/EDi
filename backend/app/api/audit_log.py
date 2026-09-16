from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogOut

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit(
    entity_type: str | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.user_id == user.user_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    return list((await db.execute(stmt)).scalars())
