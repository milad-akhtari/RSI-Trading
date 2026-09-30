from dataclasses import replace
from pathlib import Path
import time

from fastapi.testclient import TestClient

from automation.app import create_app
from automation.config import Settings
from automation.db import EventStore
from automation.models import WebhookEvent


def payload(event_id="rsi-trend|GBPUSD|5|1|ENTRY|LONG"):
    return {
        "schema_version": "1.0",
        "strategy": "RSI Trend Strategy",
        "instance_id": "test",
        "event_id": event_id,
        "event_type": "ENTRY",
        "side": "LONG",
        "ticker": "GBPUSD",
        "timeframe": "5",
        "signal_time_ms": int(time.time() * 1000),
        "signal_price": 1.25,
        "structural_stop": 1.249,
        "planned_target": 1.252,
        "rr": 2.0,
        "risk_pct": 1.0,
        "rsi": 14.0,
        "market_state": "BULLISH",
        "strength": "BASELINE",
        "trade_id": "L-1",
    }


def make_client(tmp_path: Path):
    settings = Settings(webhook_token="unit-test-token", database_path=tmp_path / "events.sqlite3")
    store = EventStore(settings.database_path)
    return TestClient(create_app(settings, store)), store


def test_auth_required(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/tradingview/wrong", json=payload())
    assert r.status_code == 401


def test_durable_accept_and_deduplication(tmp_path):
    client, store = make_client(tmp_path)
    p = payload()
    r1 = client.post("/tradingview/unit-test-token", json=p)
    r2 = client.post("/tradingview/unit-test-token", json=p)
    assert r1.status_code == 202 and r1.json()["duplicate"] is False
    assert r2.status_code == 202 and r2.json()["duplicate"] is True
    row = store.get(p["event_id"])
    assert row is not None and row["status"] == "PENDING"


def test_non_m5_rejected_by_schema(tmp_path):
    client, _ = make_client(tmp_path)
    p = payload()
    p["timeframe"] = "1"
    r = client.post("/tradingview/unit-test-token", json=p)
    assert r.status_code == 422


def test_long_stop_side_sanity_check(tmp_path):
    client, _ = make_client(tmp_path)
    p = payload()
    p["structural_stop"] = 1.26
    r = client.post("/tradingview/unit-test-token", json=p)
    assert r.status_code == 422


def test_entry_direction_and_rsi_contract_is_enforced(tmp_path):
    client, _ = make_client(tmp_path)
    p = payload()
    p["rsi"] = 16.0
    r = client.post("/tradingview/unit-test-token", json=p)
    assert r.status_code == 422


def test_rr_must_remain_two_to_one(tmp_path):
    client, _ = make_client(tmp_path)
    p = payload()
    p["rr"] = 3.0
    r = client.post("/tradingview/unit-test-token", json=p)
    assert r.status_code == 422


def test_planned_target_must_match_two_r(tmp_path):
    client, _ = make_client(tmp_path)
    p = payload()
    p["planned_target"] = 1.30
    r = client.post("/tradingview/unit-test-token", json=p)
    assert r.status_code == 422


def test_interrupted_processing_is_quarantined_not_retried(tmp_path):
    _, store = make_client(tmp_path)
    event = WebhookEvent.model_validate(payload("rsi-trend|GBPUSD|5|2|ENTRY|LONG"))
    assert store.accept(event)
    claimed = store.claim_next()
    assert claimed is not None
    assert store.mark_processing_for_reconciliation() == 1
    row = store.get(event.event_id)
    assert row is not None and row["status"] == "RECONCILIATION_REQUIRED"
    assert store.claim_next() is None


def test_authenticated_event_status_endpoint(tmp_path):
    client, store = make_client(tmp_path)
    p = payload("rsi-trend|GBPUSD|5|status|ENTRY|LONG")
    assert client.post("/tradingview/unit-test-token", json=p).status_code == 202
    store.complete(p["event_id"], {"status": "DRY_RUN_DEMO"})
    r = client.get(f"/status/unit-test-token/{p['event_id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "DONE"
    assert r.json()["result"]["status"] == "DRY_RUN_DEMO"
    assert client.get(f"/status/wrong/{p['event_id']}").status_code == 401
