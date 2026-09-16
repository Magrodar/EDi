from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import DailyBrief
from app.services.brief import build_daily_brief

router = APIRouter(prefix="/v1/briefs", tags=["briefs"])


@router.get("/daily", response_model=DailyBrief)
async def daily_brief(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await build_daily_brief(db, user.user_id)
