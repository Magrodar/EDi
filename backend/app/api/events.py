import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Event, User
from app.schemas import EventCreate, EventOut

router = APIRouter(prefix="/v1/events", tags=["events"])


@router.post("", response_model=EventOut)
async def create_event(
    payload: EventCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Event:
    # Idempotency check up front (document §17.2: all mutation endpoints require idempotency
    # keys). A pre-check rather than insert-then-catch keeps this request's session state
    # simple -- a rollback here would expire every object in the session, including `user`.
    existing_q = await db.execute(
        select(Event).where(Event.user_id == user.user_id, Event.idempotency_key == payload.idempotency_key)
    )
    existing = existing_q.scalar_one_or_none()
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    content_hash = hashlib.sha256(payload.normalized_text.encode("utf-8")).hexdigest()
    event = Event(
        user_id=user.user_id,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        occurred_at=payload.occurred_at,
        observed_at=payload.observed_at or datetime.now(timezone.utc),
        project_ids=payload.project_ids,
        actor_person_ids=payload.actor_person_ids,
        normalized_text=payload.normalized_text,
        sensitivity=payload.sensitivity,
        provenance=payload.provenance,
        idempotency_key=payload.idempotency_key,
        content_hash=content_hash,
        status="normalized",
    )
    db.add(event)
    await db.flush()

    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="create",
        entity_type="event",
        entity_id=event.event_id,
        after={"source_type": event.source_type, "idempotency_key": event.idempotency_key},
    )
    await db.commit()
    response.status_code = status.HTTP_201_CREATED
    return event


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Event:
    result = await db.execute(select(Event).where(Event.event_id == event_id, Event.user_id == user.user_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
