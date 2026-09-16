"""End-to-end smoke test against a real Postgres+pgvector database (see conftest.py).
Exercises the full Phase 0+1 loop: auth -> debrief capture -> extraction -> promotion ->
commitments/risks persisted -> daily brief -> what-am-I-missing scan -> alert ack ->
memory search -> memory delete -> audit trail.
"""

import pytest

# Shares the session-scoped event loop with the `client` fixture (see pytest.ini's
# asyncio_default_fixture_loop_scope=session) so the pooled asyncpg connection created
# during fixture setup is usable from the test body.
pytestmark = pytest.mark.asyncio(loop_scope="session")

HEADERS = {"X-API-Key": "test-api-key"}


async def test_rejects_missing_api_key(client):
    resp = await client.get("/v1/alerts")
    assert resp.status_code == 401


async def test_rejects_wrong_api_key(client):
    resp = await client.get("/v1/alerts", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


async def test_debrief_extracts_and_persists(client):
    resp = await client.post(
        "/v1/capture/transcript",
        headers=HEADERS,
        json={"text": "I'll send the RM-X purchase order by tomorrow. There is a risk that RM-X may miss the weekly plan."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["event"]["status"] == "promoted"
    assert len(body["commitments"]) == 1
    assert len(body["risks"]) == 1
    assert body["commitments"][0]["title"].startswith("I'll send")


async def test_daily_brief_reflects_persisted_commitment(client):
    await client.post(
        "/v1/capture/transcript",
        headers=HEADERS,
        json={"text": "I must finish the QC report by tomorrow."},
    )
    resp = await client.get("/v1/briefs/daily", headers=HEADERS)
    assert resp.status_code == 200
    brief = resp.json()
    assert brief["priority_1"] is not None
    assert len(brief["critical_tasks"]) >= 1


async def test_missing_scan_creates_alert_for_overdue_commitment(client):
    create = await client.post(
        "/v1/commitments",
        headers=HEADERS,
        json={"title": "Escalate RM-X shortage to supplier", "due_at": "2020-01-01T00:00:00Z"},
    )
    assert create.status_code == 200, create.text

    scan = await client.post("/v1/reason", headers=HEADERS)
    assert scan.status_code == 200
    alerts = scan.json()
    assert any(a["related_type"] == "commitment" for a in alerts)

    # calling it again immediately should be suppressed by the cooldown (no duplicate)
    scan_again = await client.post("/v1/reason", headers=HEADERS)
    assert scan_again.json() == []


async def test_alert_ack_flow(client):
    await client.post(
        "/v1/commitments",
        headers=HEADERS,
        json={"title": "Overdue thing", "due_at": "2020-01-01T00:00:00Z"},
    )
    alerts = (await client.post("/v1/reason", headers=HEADERS)).json()
    assert len(alerts) >= 1
    alert_id = alerts[0]["alert_id"]

    ack = await client.post(f"/v1/alerts/{alert_id}/ack", headers=HEADERS)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"


async def test_memory_search_and_delete(client):
    await client.post(
        "/v1/capture/transcript",
        headers=HEADERS,
        json={"text": "The supplier expects arrival of RM-X on 2026-09-22."},
    )
    search = await client.get("/v1/memory/search", headers=HEADERS, params={"q": "RM-X"})
    assert search.status_code == 200
    facts = search.json()
    assert len(facts) >= 1

    fact_id = facts[0]["fact_id"]
    delete = await client.delete(f"/v1/memory/{fact_id}", headers=HEADERS)
    assert delete.status_code == 200

    search_after = await client.get("/v1/memory/search", headers=HEADERS, params={"q": "RM-X"})
    assert all(f["fact_id"] != fact_id for f in search_after.json())


async def test_audit_log_records_mutations(client):
    await client.post(
        "/v1/commitments", headers=HEADERS, json={"title": "Something to audit"}
    )
    audit = await client.get("/v1/audit", headers=HEADERS)
    assert audit.status_code == 200
    entries = audit.json()
    assert any(e["entity_type"] == "commitment" and e["action"] == "create" for e in entries)


async def test_idempotent_event_creation(client):
    payload = {
        "source_type": "manual",
        "normalized_text": "duplicate test",
        "idempotency_key": "same-key-123",
    }
    first = await client.post("/v1/events", headers=HEADERS, json=payload)
    second = await client.post("/v1/events", headers=HEADERS, json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
