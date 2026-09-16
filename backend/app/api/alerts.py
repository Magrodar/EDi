import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Alert, User
from app.schemas import AlertOut

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    level: str | None = None,
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Alert]:
    stmt = select(Alert).where(Alert.user_id == user.user_id)
    if level:
        stmt = stmt.where(Alert.level == level)
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    stmt = stmt.order_by(Alert.created_at.desc())
    return list((await db.execute(stmt)).scalars())


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Alert:
    """Document §12.3: command alerts require acknowledgment, but the system should not spam."""
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id, Alert.user_id == user.user_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    before = {"status": alert.status}
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="ack",
        entity_type="alert",
        entity_id=alert.alert_id,
        before=before,
        after={"status": alert.status},
    )
    await db.commit()
    return alert
