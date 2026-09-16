"""Hybrid retrieval (document §19): relational filter first, then semantic rerank.
Graph expansion is out of scope for this MVP (§45: model relationships in Postgres first,
add a graph DB only once query complexity proves the need — no graph queries exist yet to
justify it).
"""

import math
import uuid

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fact
from app.services.embeddings import get_embedding_provider

RELATIONAL_PREFILTER_CAP = 200


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return -1.0
    return dot / (norm_a * norm_b)


async def search_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    limit: int = 20,
) -> list[Fact]:
    stmt = select(Fact).where(
        Fact.user_id == user_id,
        Fact.status.in_(["canonical", "provisional", "conflicted"]),
        Fact.deleted_at.is_(None),
    )
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Fact.subject_label.ilike(pattern),
                Fact.predicate.ilike(pattern),
                cast(Fact.value_json, Text).ilike(pattern),
            )
        )
    stmt = stmt.order_by(Fact.recorded_at.desc()).limit(RELATIONAL_PREFILTER_CAP)
    candidates = list((await db.execute(stmt)).scalars())

    provider = get_embedding_provider()
    if provider.is_semantic and query and candidates:
        query_vec = await provider.embed(query)
        candidates.sort(
            key=lambda f: -_cosine(query_vec, list(f.embedding)) if f.embedding is not None else 1.0
        )

    return candidates[:limit]
