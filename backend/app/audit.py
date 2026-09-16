import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Append-only audit trail. Called inside the same transaction as the mutation
    it describes, so it either commits with it or rolls back with it — never orphaned."""
    db.add(
        AuditLog(
            user_id=user_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
        )
    )
