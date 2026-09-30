import json
from pathlib import Path

import pytest

import windows_readonly
from tests.test_readonly_dry_run import setup


def installation(tmp_path, monkeypatch, extra=""):
    # Clear only configuration names used here so the selected .env is exercised.
    from dataclasses import fields
    from automation.config import Settings
    for item in fields(Settings):
        monkeypatch.delenv(item.name.upper(), raising=False)
    for name in ("ALLOWED_MT5_SYMBOLS", "SYMBOL_MAP_JSON", "MT5_DEVIATION_POINTS"):
        monkeypatch.delenv(name, raising=False)
    original_db = tmp_path / "original.sqlite3"
    original_db.write_bytes(b"original data")
    env = tmp_path / ".env"
    env.write_text("WEBHOOK_TOKEN=private-local-test-token\n"
                   "EXECUTION_MODE=demo\nDEMO_ORDER_SUBMISSION_ENABLED=false\n"
                   "LIVE_TRADING_ENABLED=false\nNEW_ENTRIES_ENABLED=false\n"
                   "EXECUTE_TRADINGVIEW_EXIT_ALERTS=false\n"
                   f"DATABASE_PATH={original_db.as_posix()}\n" + extra)
    return env, original_db


def test_explicit_old_installation_runs_new_code_without_replacing_files(tmp_path, monkeypatch):
    env, db = installation(tmp_path, monkeypatch)
    before = env.read_bytes()
    _, broker = setup()
    received = []
    def factory(settings):
        received.append(settings)
        return broker
    result = windows_readonly.check_installation(tmp_path, factory)
    assert result["status"] == "GATEWAY_CHECK_PASSED"
    assert len(result["checks"]) == 2
    assert received[0].webhook_token == "private-local-test-token"
    assert received[0].mt5_quote_time_offset_seconds == 10800
    assert received[0].mt5_quote_time_offset_server == "MetaQuotes-Demo"
    assert env.read_bytes() == before and db.read_bytes() == b"original data"
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


@pytest.mark.parametrize("extra", [
    "DEMO_ORDER_SUBMISSION_ENABLED=true\n", "LIVE_TRADING_ENABLED=true\n",
    "EXECUTION_MODE=live\n", "EXECUTE_TRADINGVIEW_EXIT_ALERTS=true\n",
])
def test_armed_saved_settings_refused_before_broker_factory(tmp_path, monkeypatch, extra):
    installation(tmp_path, monkeypatch, extra)
    def forbidden(settings):
        pytest.fail("Armed configurations must not instantiate a broker")
    with pytest.raises(ValueError, match="submission switches"):
        windows_readonly.check_installation(tmp_path, forbidden)


def test_armed_process_environment_cannot_be_hidden_by_safe_env_file(tmp_path, monkeypatch):
    installation(tmp_path, monkeypatch)
    monkeypatch.setenv("DEMO_ORDER_SUBMISSION_ENABLED", "true")
    with pytest.raises(ValueError, match="submission switches"):
        windows_readonly.check_installation(tmp_path, lambda _: pytest.fail("broker created"))


def test_missing_settings_is_reported_without_creating_them(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        windows_readonly.check_installation(tmp_path, lambda _: pytest.fail("broker created"))
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("error", [RuntimeError("PRIVATE_PASSWORD"), ImportError("PRIVATE_TOKEN")])
def test_cli_reports_errors_without_secret_details(tmp_path, monkeypatch, capsys, error):
    monkeypatch.setattr(windows_readonly, "__file__", str(tmp_path / "windows_readonly.py"))
    def fail(_):
        raise error
    monkeypatch.setattr(windows_readonly, "check_installation", fail)
    assert windows_readonly.main(["--settings-directory", str(tmp_path)]) == 2
    report = json.loads((tmp_path / "US30_READONLY_RESULT.json").read_text())
    assert report["reason"] == type(error).__name__
    output = capsys.readouterr().out
    assert "PRIVATE" not in output and "PRIVATE" not in json.dumps(report)


def test_report_write_failure_keeps_printed_result_and_returns_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(windows_readonly, "__file__", str(tmp_path / "missing" / "windows_readonly.py"))
    monkeypatch.setattr(windows_readonly, "check_installation", lambda _: {"status": "GATEWAY_CHECK_PASSED"})
    assert windows_readonly.main(["--settings-directory", str(tmp_path)]) == 1
    assert "GATEWAY_CHECK_PASSED" in capsys.readouterr().out
