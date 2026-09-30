from dataclasses import replace
import time

import pytest

from automation.broker import SymbolSnapshot
from automation.dry_run_mt5 import ReadOnlyBroker, run_check
from automation.engine import ExecutionEngine, ExecutionRejected
from tests.fakes import FakeBroker
from tests.test_execution_engine import make_settings


def setup():
    settings = make_settings(demo_order_submission_enabled=False, new_entries_enabled=False)
    broker = FakeBroker()
    broker.account_snapshot.equity = broker.account_snapshot.margin_free = 1000
    broker.symbols["US30"] = SymbolSnapshot("US30", .01, .01, 2, .1, 250, .1,
                                           51533.2, 51535.2, int(time.time() * 1000))
    return settings, broker


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_native_style_us30_sizing_does_not_arm_settings_or_send_orders(side):
    settings, broker = setup()
    result = run_check(settings, broker, symbol_name="US30", side=side, stop_distance=100, risk_pct=1)
    calc = result["result"]
    assert calc["status"] == "DRY_RUN_DEMO"
    assert calc["volume"] == pytest.approx(.1)
    assert calc["risk_cash_budget"] == 10
    assert calc["margin_required"] == 10
    assert abs(calc["tp"] - calc["entry_quote"]) == pytest.approx(2 * abs(calc["entry_quote"] - calc["sl"]))
    assert not settings.new_entries_enabled and not settings.demo_order_submission_enabled
    assert "US30" not in settings.allowed_symbols
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


@pytest.mark.parametrize("overrides", [
    {"demo_order_submission_enabled": True}, {"live_trading_enabled": True},
    {"execution_mode": "live"}, {"execute_tradingview_exit_alerts": True},
])
def test_armed_environment_is_rejected_before_connecting(overrides):
    settings, broker = setup()
    with pytest.raises(ValueError, match="submission switches"):
        run_check(replace(settings, **overrides), broker, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=1)
    assert not broker.connected


@pytest.mark.parametrize("method", ["open_market", "set_protection", "close_position"])
def test_adapter_blocks_all_broker_mutations_even_if_engine_changes(method):
    _, broker = setup()
    with pytest.raises(RuntimeError, match="Read-only check blocks"):
        getattr(ReadOnlyBroker(broker), method)()
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


def test_engine_regression_cannot_send_through_readonly_adapter(monkeypatch):
    settings, broker = setup()
    def unsafe_process(engine, event):
        return engine.broker.open_market(side=event.side.value)
    monkeypatch.setattr(ExecutionEngine, "process", unsafe_process)
    with pytest.raises(RuntimeError, match="blocks order submission"):
        run_check(settings, broker, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=1)
    assert broker.open_calls == 0


@pytest.mark.parametrize("failure", ["live_account", "wrong_account", "stale_quote", "minimum_lot", "margin"])
def test_real_broker_safety_failures_still_reject(failure):
    settings, broker = setup()
    if failure == "live_account":
        broker.account_snapshot.is_demo = False
    elif failure == "wrong_account":
        broker.account_snapshot.login += 1
    elif failure == "stale_quote":
        broker.symbols["US30"].quote_time_ms = int((time.time() - 60) * 1000)
    elif failure == "minimum_lot":
        broker.symbols["US30"].volume_min = 1
    else:
        broker.account_snapshot.margin_free = 1
    with pytest.raises(ExecutionRejected):
        run_check(settings, broker, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=1)
    assert broker.open_calls == broker.close_calls == broker.protection_calls == 0


def test_risk_over_cap_is_rejected_before_connecting():
    settings, broker = setup()
    with pytest.raises(ValueError, match="MAX_RISK_PCT"):
        run_check(settings, broker, symbol_name="US30", side="LONG", stop_distance=100, risk_pct=2)
    assert not broker.connected
