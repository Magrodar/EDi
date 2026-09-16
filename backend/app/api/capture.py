import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user
from app.db import get_db
from app.llm import get_extraction_provider
from app.models import Event, User
from app.schemas import CaptureTranscriptIn, CaptureTranscriptOut
from app.services.extraction import persist_extraction
from app.services.scan import run_missing_scan

router = APIRouter(prefix="/v1/capture", tags=["capture"])


@router.post("/transcript", response_model=CaptureTranscriptOut)
async def capture_transcript(
    payload: CaptureTranscriptIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Typed/push-to-talk debrief entry point (document §22.1 'debrief' flow, text-only —
    no audio capture in this build). Runs the full pipeline synchronously: event ->
    extraction -> promotion -> what-am-I-missing scan, all in one DB transaction."""
    now = datetime.now(timezone.utc)
    idempotency_key = payload.idempotency_key or f"debrief:{uuid.uuid4()}"
    content_hash = hashlib.sha256(payload.text.encode("utf-8")).hexdigest()

    event = Event(
        user_id=user.user_id,
        source_type="manual",
        occurred_at=payload.occurred_at,
        observed_at=now,
        project_ids=payload.project_ids,
        normalized_text=payload.text,
        sensitivity="personal",
        idempotency_key=idempotency_key,
        content_hash=content_hash,
        status="normalized",
    )
    db.add(event)
    await db.flush()

    provider = get_extraction_provider()
    extraction_result = await provider.extract(payload.text, occurred_at=payload.occurred_at)

    persisted = await persist_extraction(db, user_id=user.user_id, event=event, result=extraction_result)
    event.status = "promoted"
    event.classifications = list(
        {
            *(["fact"] if persisted["facts"] else []),
            *(["commitment"] if persisted["commitments"] else []),
            *(["risk"] if persisted["risks"] else []),
        }
    )

    scan_alerts = await run_missing_scan(db, user.user_id)

    await record_audit(
        db,
        user_id=user.user_id,
        actor="user",
        action="create",
        entity_type="event",
        entity_id=event.event_id,
        after={
            "facts": len(persisted["facts"]),
            "commitments": len(persisted["commitments"]),
            "risks": len(persisted["risks"]),
        },
    )
    await db.commit()

    return {
        "event": event,
        "facts": persisted["facts"],
        "commitments": persisted["commitments"],
        "risks": persisted["risks"],
        "alerts_created": persisted["alerts_created"] + len(scan_alerts),
    }
