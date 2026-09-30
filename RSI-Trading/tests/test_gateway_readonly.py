from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import sqlite3
import time

import pytest

from automation.check_us30_gateway import run_check
from automation.engine import ExecutionEngine, ExecutionRejected
from automation.db import EventStore
from tests.test_readonly_dry_run import setup


def test_http_to_worker_checks_both_sides_without_touching_original_settings_or_database(tmp_path):
    settings, broker = setup()
    real_db = tmp_path / "production.sqlite3"
    real_db.write_bytes(b"original file must stay unchanged")
    settings = replace(settings, database_path=real_db)
    result = run_check(settings, broker)
    assert result["status"] == "GATEWAY_CHECK_PASSED"
    assert result["gateway_database_changed"] is False
    assert result["settings_file_changed"] is False
    assert not settings.new_entries_enabled and not settings.demo_order_submission_enabled
    assert settings.allowed_symbols != ["US30"]
    assert real_db.read_bytes() == b"original file must stay unchanged"
    assert [x["side"] for x in result["checks"]] == ["LONG", "SHORT"]
    for item in result["checks"]:
        assert item["http_receipt"] == 202 and item["duplicate_detected"]
        assert item["conflicting_payload_rejected"]
        assert item["durable_status"] == "DONE" and item["attempts"] == 1
        assert item["saved_result_verified"] and item["completed_event_not_retried"]
        assert item["result"]["volume"] == pytest.approx(.1)
        assert item["result"]["risk_cash_budget"] == 10
        assert item["margin_required"] == 10
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


@pytest.mark.parametrize("override", [
    {"demo_order_submission_enabled": True}, {"live_trading_enabled": True},
    {"execute_tradingview_exit_alerts": True}, {"execution_mode": "live"},
])
def test_armed_settings_refused_before_server_or_broker_start(monkeypatch, override):
    import automation.check_us30_gateway as check
    settings, broker = setup()
    def forbidden_start(*args, **kwargs):
        pytest.fail("Armed configuration must be refused before binding a socket")
    monkeypatch.setattr(check, "loopback_server", forbidden_start)
    with pytest.raises(ValueError, match="submission switches"):
        run_check(replace(settings, **override), broker)
    assert not broker.connected


def test_stale_native_quote_rejected_by_the_worker(tmp_path):
    settings, broker = setup()
    settings = replace(settings, database_path=tmp_path / "untouched.sqlite3")
    broker.symbols["US30"].quote_time_ms = int((time.time() - 60) * 1000)
    with pytest.raises(ExecutionRejected, match="quote is stale"):
        run_check(settings, broker)
    assert not settings.database_path.exists()
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


def test_live_account_rejected_without_broker_writes():
    settings, broker = setup()
    broker.account_snapshot.is_demo = False
    with pytest.raises(ExecutionRejected, match="not a demo"):
        run_check(settings, broker)
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


def test_worker_cannot_write_even_after_engine_regression(monkeypatch, tmp_path):
    settings, broker = setup()
    settings = replace(settings, database_path=tmp_path / "production.sqlite3")
    def unsafe_process(engine, event):
        engine.broker.open_market(side="LONG")
    monkeypatch.setattr(ExecutionEngine, "process", unsafe_process)
    with pytest.raises(RuntimeError, match="single read-only dry run"):
        run_check(settings, broker)
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0
    assert not settings.database_path.exists()


def test_importing_check_never_initializes_original_gateway_database(tmp_path):
    database = tmp_path / "original-gateway.sqlite3"
    env = {**os.environ, "WEBHOOK_TOKEN": "valid-private-test-token",
           "DATABASE_PATH": str(database)}
    subprocess.run([sys.executable, "-c", "import automation.check_us30_gateway"],
                   cwd=Path(__file__).resolve().parents[1], env=env, check=True,
                   capture_output=True, timeout=10)
    assert not database.exists()


def test_cli_network_error_cannot_expose_authentication_url(monkeypatch, capsys):
    import automation.check_us30_gateway as check
    from urllib.error import URLError
    settings, _ = setup()
    monkeypatch.setattr(check, "Settings", lambda: settings)
    monkeypatch.setattr(check, "MT5Broker", lambda s: object())
    def fail(*args, **kwargs):
        raise URLError("http://127.0.0.1/tradingview/PRIVATE_TOKEN")
    monkeypatch.setattr(check, "run_check", fail)
    monkeypatch.setattr("sys.argv", ["check"])
    assert check.main() == 1
    output = capsys.readouterr().out
    assert "URLError" in output and "PRIVATE_TOKEN" not in output


@pytest.mark.parametrize("interrupted", [False, True])
def test_store_transactions_release_handles_and_preserve_commit_or_rollback(tmp_path, interrupted):
    store = EventStore(tmp_path / "events.sqlite3")
    def transaction():
        with store._connect() as conn:
            transaction.connection = conn
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO safety_state VALUES (1, 'test-pause', 'test-time')")
            if interrupted:
                raise RuntimeError("interrupted transaction")
    if interrupted:
        with pytest.raises(RuntimeError, match="interrupted"):
            transaction()
    else:
        transaction()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        transaction.connection.execute("SELECT 1")
    assert store.entry_pause_reason() == (None if interrupted else "test-pause")
