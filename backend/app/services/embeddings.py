"""Pluggable embedding provider. Stub keeps the retrieval pipeline runnable with no API key;
it produces a deterministic pseudo-embedding (same text -> same vector) so equality/dedup
logic can be exercised, but it carries no real semantic meaning. Swap to a real provider by
setting EDI_EMBEDDINGS_PROVIDER=openai; app/services/search.py degrades to lexical-only
retrieval automatically whenever embeddings aren't meaningfully comparable (i.e. stub mode).
"""

import hashlib
import random
from typing import Protocol

from app.config import settings

EMBEDDING_DIM = 1536


class EmbeddingProvider(Protocol):
    is_semantic: bool

    async def embed(self, text: str) -> list[float]: ...


class StubEmbeddingProvider:
    is_semantic = False

    async def embed(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]


class OpenAIEmbeddingProvider:
    is_semantic = True

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        if not settings.openai_api_key:
            raise RuntimeError("EDI_EMBEDDINGS_PROVIDER=openai requires OPENAI_API_KEY to be set")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding


def get_embedding_provider() -> EmbeddingProvider:
    if settings.edi_embeddings_provider == "openai":
        return OpenAIEmbeddingProvider()
    return StubEmbeddingProvider()
