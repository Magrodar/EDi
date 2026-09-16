from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import alerts, audit_log, briefs, capture, commitments, decisions, events, memory, reason, risks
from app.auth import hash_key
from app.config import settings
from app.db import SessionLocal
from app.models import User


async def _seed_user() -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == settings.edi_user_email))
        if result.scalar_one_or_none() is None:
            db.add(User(email=settings.edi_user_email, api_key_hash=hash_key(settings.edi_api_key)))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_user()
    yield


app = FastAPI(title="Ultimate EDI — Core API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-user local/dev system; tighten before any multi-origin deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (events, capture, memory, commitments, decisions, risks, briefs, alerts, reason, audit_log):
    app.include_router(router.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
