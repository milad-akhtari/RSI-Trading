from types import SimpleNamespace as NS
import time

import pytest

from automation.dry_run_mt5 import run_check
from automation.engine import ExecutionRejected
from automation.mt5_client import MT5Broker
from tests.fakes import FakeBroker
from tests.test_execution_engine import make_settings


class TickModule:
    def __init__(self, raw_ms, server="Fake-Demo", fallback=False):
        self.server = server
        self.tick = NS(time_msc=0 if fallback else raw_ms, time=raw_ms // 1000,
                       bid=51551.5, ask=51552.7)

    def account_info(self):
        return NS(server=self.server)

    def symbol_info(self, name):
        return NS(visible=True, point=.01, trade_tick_size=.01, digits=2,
                  volume_min=.1, volume_max=250, volume_step=.1)

    def symbol_info_tick(self, name):
        return self.tick


def native_adapter(offset, raw_ms, **kwargs):
    settings = make_settings(demo_order_submission_enabled=False, new_entries_enabled=False,
                             mt5_quote_time_offset_seconds=offset,
                             mt5_quote_time_offset_server="Fake-Demo" if offset else "")
    broker = MT5Broker(settings)
    broker.mt5 = TickModule(raw_ms, **kwargs)
    return settings, broker


@pytest.mark.parametrize("offset", [0, 10800, -10800])
@pytest.mark.parametrize("fallback", [False, True])
def test_explicit_clock_conversion_preserves_elapsed_quote_age(offset, fallback):
    now_ms = int(time.time()) * 1000
    settings, broker = native_adapter(offset, now_ms + offset * 1000 - 2000, fallback=fallback)
    assert broker.symbol("US30").quote_time_ms == now_ms - 2000
    assert settings.max_quote_age_seconds == 30 and settings.max_future_skew_seconds == 10


def test_server_change_rejects_offset_on_each_symbol_read():
    _, broker = native_adapter(10800, int(time.time() * 1000) + 10800000)
    broker.symbol("US30")
    broker.mt5.server = "Other-Demo"
    with pytest.raises(RuntimeError, match="offset refused"):
        broker.symbol("US30")


@pytest.mark.parametrize("raw_ms", [0, -1])
def test_offset_cannot_repair_missing_or_negative_tick_time(raw_ms):
    _, broker = native_adapter(-10800, raw_ms)
    assert broker.symbol("US30").quote_time_ms <= 0


@pytest.mark.parametrize("age", [2, 60, -20])
def test_corrected_quote_still_passes_original_engine_freshness_gates(age):
    settings, native = native_adapter(10800, int((time.time() + 10800 - age) * 1000))
    fake = FakeBroker()
    fake.account_snapshot.equity = fake.account_snapshot.margin_free = 1000
    fake.symbol = native.symbol
    if age == 2:
        out = run_check(settings, fake, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=1)
        assert out["result"]["status"] == "DRY_RUN_DEMO"
        assert out["quote_clock"]["offset_seconds"] == 10800
        assert out["settings_file_changed"] is False
    else:
        with pytest.raises(ExecutionRejected, match="quote is stale"):
            run_check(settings, fake, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=1)
    assert fake.open_calls == fake.close_calls == fake.protection_calls == 0


@pytest.mark.parametrize("offset,server", [(10800, ""), (50401, "Fake-Demo"),
                                          (-50401, "Fake-Demo"), (1.5, "Fake-Demo"),
                                          (True, "Fake-Demo")])
def test_invalid_offset_configuration_refused(offset, server):
    settings = make_settings(mt5_quote_time_offset_seconds=offset,
                             mt5_quote_time_offset_server=server)
    with pytest.raises(ValueError, match="OFFSET"):
        settings.validate()


def test_cli_clock_override_is_temporary_and_passed_to_native_adapter(monkeypatch, capsys):
    import automation.dry_run_mt5 as cli
    baseline = make_settings(demo_order_submission_enabled=False, new_entries_enabled=False)
    received = []
    monkeypatch.setattr(cli, "Settings", lambda: baseline)
    monkeypatch.setattr(cli, "MT5Broker", lambda s: received.append(s) or object())
    monkeypatch.setattr(cli, "run_check", lambda *args, **kwargs: {"test": True})
    monkeypatch.setattr("sys.argv", ["check", "--symbol", "US30", "--stop-distance", "100",
                                   "--quote-time-offset-seconds", "10800",
                                   "--quote-time-offset-server", "Fake-Demo"])
    assert cli.main() == 0
    assert received[0].mt5_quote_time_offset_seconds == 10800
    assert received[0].mt5_quote_time_offset_server == "Fake-Demo"
    assert baseline.mt5_quote_time_offset_seconds == 0
    assert not baseline.demo_order_submission_enabled
