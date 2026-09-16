# Ultimate EDI — Core (Phase 0 + Phase 1)

Mahmoud's personal intelligence & command system. This is the **system-of-record core**:
event capture, structured memory with provenance, commitment/decision/risk tracking, a
deterministic daily brief, and a basic "what am I missing?" scan — built per
`docs/Ultimate_EDI_Technical_Design_v1.1.md`'s own recommended build order:

> Structured memory and debriefs → calendar/email/doc sensors → risk/dependency
> intelligence → controlled actions → ambient capture and wearables.

## What's in this repo (and what isn't)

**Built (Phase 0 + Phase 1 MVP core):**
- PostgreSQL schema (`migrations/001_init.sql`) — users, people, projects, events, facts,
  commitments, decisions, risks, alerts, audit_log. UUID PKs, UTC timestamps, idempotency keys.
- FastAPI backend with single-user API-key auth and an audit log on every mutation.
- Canonical Event API + typed-debrief capture endpoint.
- Extraction pipeline behind a **pluggable LLM interface** (`app/llm/`) — ships with a
  deterministic stub provider so the whole pipeline runs and is testable with **no API key**.
  Drop in `OPENAI_API_KEY` to switch to the real provider — no code changes needed.
- Memory promotion engine implementing the document's `promotion_score` formula.
- Commitment / Decision / Risk journal with source-event provenance.
- Hybrid memory search (relational filter → lexical; semantic step activates automatically
  once embeddings are wired to a real provider).
- Deterministic daily brief (Priority #1, ≤3 critical tasks, decisions needed, changed risks,
  waiting-on, one EDI observation) per the document's brief rules.
- A basic deterministic "what am I missing?" scan (overdue commitments, rising-exposure risks,
  contradicting canonical facts) that creates Alerts using the document's `intervention_score`
  formula and alert-level thresholds, with cooldown/dedup.
- Memory delete (soft-delete: removed from retrieval, audit trail preserved).
- A minimal single-page frontend (no build step) for debrief entry, the daily brief, the three
  journals, alerts, and search.

**Not built here** (each needs infrastructure/decisions only you can provide — OAuth apps,
Play Store account, device testing, a real API key, a security review):
- Gmail / Calendar / Drive connectors (Phase 2)
- Risk/dependency/contradiction *engines* beyond the basic scan above, opportunity radar (Phase 3)
- Any external write action — send email, reschedule meetings (Phase 4)
- Mobile app, voice capture, ambient audio (Phase 4/5 — explicit R&D track per the document)

Treat this as the **Prototype** stage the document defines (§44): "Debrief → structured
memory → brief works on 3 pilot missions." Everything above it is a separate, later decision.

## Running it locally

```bash
cp .env.example .env          # edit EDI_API_KEY at minimum
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Frontend: open `frontend/index.html` directly in a browser, or serve it
  (`python3 -m http.server 8080` from `frontend/`) and enter your API key when prompted.

On first boot the API seeds one user from `EDI_USER_EMAIL` / `EDI_API_KEY`.

## Wiring a real LLM later

Set `OPENAI_API_KEY` and `EDI_LLM_PROVIDER=openai` in `.env`. Until then,
`EDI_LLM_PROVIDER=stub` (default) uses a deterministic heuristic extractor — good enough to
exercise the full pipeline (event → extraction → promotion → facts/commitments/risks) without
spending a key, but it will not match the reasoning quality of a real model. Model **choice**
(GPT-6 Astra / 5.6 Terra / Luna per the document) stays configuration (`EDI_LLM_MODEL`), never
hard-coded.

## Tests

```bash
cd backend && pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Design gates this build respects

- No autonomous external actions (document §13: A2 max — reversible, internal-only).
- Uncertain facts stay `provisional`, never silently become `canonical` (§9.2/§9.3).
- Untrusted content (debrief text, future connector content) is never concatenated with
  policy/system instructions as a peer — the extraction prompt wraps it as evidence (§37.1).
- Deletion removes retrieval, preserves audit metadata (§20.2, §42).
