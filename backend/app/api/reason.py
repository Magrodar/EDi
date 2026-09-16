from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import AlertOut
from app.services.scan import run_missing_scan

router = APIRouter(prefix="/v1/reason", tags=["reason"])


@router.post("", response_model=list[AlertOut])
async def reason(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    """Manual 'EDI, what am I missing?' trigger (document §22.2 voice command, §11 scan-on-
    demand). Runs the deterministic scan across all open commitments/risks/decisions and
    returns any new (non-suppressed) alerts."""
    alerts = await run_missing_scan(db, user.user_id)
    await db.commit()
    return alerts
