import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://edi:change_me@localhost:5432/edi_test")
os.environ.setdefault("EDI_API_KEY", "test-api-key")
os.environ.setdefault("EDI_USER_EMAIL", "test@example.com")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import engine


@pytest_asyncio.fixture
async def client():
    # pytest-asyncio gives each test function its own event loop; the engine's pooled
    # connections from a previous test's loop are unusable here, so drop them first.
    await engine.dispose()

    # Every test starts from a clean set of mutable tables; users is reseeded by lifespan.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE audit_log, alerts, risks, decisions, commitments, facts, events, "
                "projects, people, users RESTART IDENTITY CASCADE"
            )
        )

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac
