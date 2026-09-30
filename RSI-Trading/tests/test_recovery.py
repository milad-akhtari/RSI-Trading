import sqlite3
import time

import pytest

from automation.db import EventConflict, EventStore
from automation.engine import ExecutionEngine
from automation.lease import WorkerLease
from automation.worker import process_next
from automation.recovery import resume_after_review
from tests.fakes import FakeBroker
from tests.test_execution_engine import entry_event, make_settings
from tests.test_webhook import make_client, payload


def test_conflicting_event_id_does_not_replace_original(tmp_path):
    client, store = make_client(tmp_path)
    first = payload()
    assert client.post("/tradingview/unit-test-token", json=first).status_code == 202
    changed = dict(first, risk_pct=0.5)
    assert client.post("/tradingview/unit-test-token", json=changed).status_code == 409
    assert store.get(first["event_id"])["status"] == "PENDING"


def test_new_event_id_cannot_replay_same_logical_trade(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    first = entry_event(event_id="original-event")
    assert store.accept(first)
    duplicate = first.model_copy(update={"event_id": "different-event-id"})
    with pytest.raises(EventConflict):
        store.accept(duplicate)
    assert store.get(duplicate.event_id) is None


def test_uncertain_entry_pauses_other_instances_and_survives_restart(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    broker = FakeBroker()
    broker.open_result_uncertain = True
    engine = ExecutionEngine(make_settings(reconciliation_wait_seconds=0), broker)
    event = entry_event(event_id="uncertain-entry")
    store.accept(event)
    assert process_next(store, engine)
    assert store.get(event.event_id)["status"] == "RECONCILIATION_REQUIRED"
    restarted = EventStore(store.path)
    assert restarted.entry_pause_reason()
    other = entry_event(event_id="other-instance-entry", instance_id="other", trade_id="L-2")
    restarted.accept(other)
    assert process_next(restarted, engine)
    assert broker.open_calls == 1
    assert restarted.get(other.event_id)["status"] == "FAILED"
    exit_event = entry_event(event_id="exit-while-paused", event_type="EXIT")
    restarted.accept(exit_event)
    assert process_next(restarted, engine)
    assert restarted.get(exit_event.event_id)["status"] == "DONE"


def test_definite_entry_rejection_does_not_mark_unknown_order(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    event = entry_event(signal_time_ms=int((time.time() - 600) * 1000))
    store.accept(event)
    broker = FakeBroker()
    process_next(store, ExecutionEngine(make_settings(), broker))
    assert store.get(event.event_id)["status"] == "FAILED"
    assert store.entry_pause_reason() is None and broker.open_calls == 0


def test_startup_quarantine_pauses_entries_without_requeue(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    event = entry_event()
    store.accept(event)
    store.claim_next()
    restarted = EventStore(store.path)
    assert restarted.mark_processing_for_reconciliation() == 1
    assert restarted.entry_pause_reason()
    assert restarted.claim_next() is None
    restarted.resume_entries()
    assert restarted.entry_pause_reason() is None
    assert restarted.get(event.event_id)["status"] == "RECONCILIATION_REQUIRED"


def test_second_worker_cannot_run_but_lease_releases_on_shutdown(tmp_path):
    path = tmp_path / "events.sqlite3"
    with WorkerLease(path):
        with pytest.raises(RuntimeError, match="Another execution worker"):
            with WorkerLease(path):
                pass
    with WorkerLease(path):
        pass


def test_storage_contention_is_not_acknowledged_as_accepted(tmp_path):
    client, store = make_client(tmp_path)
    blocker = sqlite3.connect(store.path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        start = time.monotonic()
        result = client.post("/tradingview/unit-test-token", json=payload())
        assert result.status_code == 503
        assert time.monotonic() - start < 2.5
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_health_exposes_durable_reconciliation_pause(tmp_path):
    client, store = make_client(tmp_path)
    store.pause_entries("review broker first")
    assert client.get("/health").json()["entries_paused_for_reconciliation"] is True


def test_operator_recovery_only_reads_broker_and_does_not_retry(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    settings = make_settings(database_path=store.path)
    broker = FakeBroker()
    event = entry_event()
    store.accept(event)
    store.claim_next()
    store.mark_processing_for_reconciliation()
    resume_after_review(settings, store, broker)
    assert store.entry_pause_reason() is None
    assert store.get(event.event_id)["status"] == "RECONCILIATION_REQUIRED"
    assert broker.open_calls == 0 and broker.close_calls == 0


def test_unprotected_position_prevents_resume(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    settings = make_settings(database_path=store.path)
    broker = FakeBroker()
    broker.open_market(side="LONG", symbol="GBPUSD", volume=.1, sl=0, tp=1.26,
                       magic=settings.mt5_magic, deviation_points=1, comment="synthetic")
    store.pause_entries("reconcile")
    with pytest.raises(RuntimeError, match="missing protection"):
        resume_after_review(settings, store, broker)
    assert store.entry_pause_reason()
