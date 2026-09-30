from __future__ import annotations

import time
from pathlib import Path

import pytest

from automation.config import Settings
from automation.engine import ExecutionEngine, ExecutionRejected
from automation.models import WebhookEvent
from tests.fakes import FakeBroker


def make_settings(**overrides):
    base = dict(
        webhook_token="x",
        execution_mode="demo",
        demo_order_submission_enabled=True,
        live_trading_enabled=False,
        new_entries_enabled=True,
        max_event_age_seconds=120,
        max_risk_pct=1.0,
        max_total_risk_pct=2.0,
        max_open_positions=1,
        max_margin_fraction=0.5,
        max_risk_overrun_pct=10.0,
        max_spread_points=1000,
        deviation_points=20,
        mt5_magic=560015,
        mt5_login=100000,
        mt5_server="Fake-Demo",
        allowed_symbols=["GBPUSD", "XAUUSD", "US30.cash", "BTCUSD"],
        symbol_map={"TV:GBPUSD": "GBPUSD", "GBPUSD": "GBPUSD"},
    )
    base.update(overrides)
    return Settings(**base)


def entry_event(**overrides):
    p = dict(
        schema_version="1.0",
        strategy="RSI Trend Strategy",
        instance_id="test",
        event_id="evt-12345678",
        event_type="ENTRY",
        side="LONG",
        ticker="TV:GBPUSD",
        timeframe="5",
        signal_time_ms=int(time.time() * 1000),
        signal_price=1.2501,
        structural_stop=1.2491,
        planned_target=1.2521,
        rr=2.0,
        risk_pct=1.0,
        rsi=14.0,
        market_state="BULLISH",
        strength="BASELINE",
        trade_id="L-1",
    )
    p.update(overrides)
    if "planned_target" not in overrides and p["event_type"] == "ENTRY":
        if p["side"] == "LONG":
            p["planned_target"] = p["signal_price"] + 2.0 * (p["signal_price"] - p["structural_stop"])
        else:
            p["planned_target"] = p["signal_price"] - 2.0 * (p["structural_stop"] - p["signal_price"])
    return WebhookEvent.model_validate(p)


def test_demo_dry_run_does_not_submit_order():
    broker = FakeBroker()
    settings = make_settings(demo_order_submission_enabled=False)
    result = ExecutionEngine(settings, broker).process(entry_event())
    assert result["status"] == "DRY_RUN_DEMO"
    assert broker.open_calls == 0


def test_demo_entry_places_and_confirms_broker_side_protection():
    broker = FakeBroker()
    settings = make_settings()
    result = ExecutionEngine(settings, broker).process(entry_event())
    assert result["status"] == "DEMO_ORDER_OPENED"
    assert broker.open_calls == 1
    assert broker.protection_calls == 1
    pos = broker.positions(symbol="GBPUSD", magic=settings.mt5_magic)[0]
    assert pos.sl == pytest.approx(1.2491)
    # Actual fill is 1.25010, so 2R target = 1.25210.
    assert pos.tp == pytest.approx(1.2521)


def test_position_size_is_rounded_down_to_broker_step():
    broker = FakeBroker()
    settings = make_settings()
    result = ExecutionEngine(settings, broker).process(entry_event(structural_stop=1.24913))
    pos = broker.positions(symbol="GBPUSD", magic=settings.mt5_magic)[0]
    assert abs((pos.volume / 0.01) - round(pos.volume / 0.01)) < 1e-9
    assert result["volume"] == pos.volume


def test_real_account_is_rejected_while_service_is_demo():
    broker = FakeBroker()
    broker.account_snapshot.is_demo = False
    with pytest.raises(ExecutionRejected, match="not a demo account"):
        ExecutionEngine(make_settings(), broker).process(entry_event())


def test_stale_entry_is_rejected_but_no_order_is_sent():
    broker = FakeBroker()
    old = int((time.time() - 1000) * 1000)
    with pytest.raises(ExecutionRejected, match="Stale entry"):
        ExecutionEngine(make_settings(max_event_age_seconds=30), broker).process(entry_event(signal_time_ms=old))
    assert broker.open_calls == 0


def test_existing_symbol_position_blocks_accidental_netting_or_reversal():
    broker = FakeBroker()
    settings = make_settings()
    broker.open_market(side="LONG", symbol="GBPUSD", volume=0.01, sl=1.249, tp=1.252, magic=999, deviation_points=1, comment="manual")
    with pytest.raises(ExecutionRejected, match="already exists"):
        ExecutionEngine(settings, broker).process(entry_event(event_id="evt-22222222"))


def test_protection_failure_emergency_closes_position():
    broker = FakeBroker()
    broker.protection_result_ok = False
    with pytest.raises(RuntimeError, match="emergency-closed"):
        ExecutionEngine(make_settings(), broker).process(entry_event(event_id="evt-33333333"))
    assert broker.close_calls == 1
    assert broker.positions(symbol="GBPUSD") == []


def test_gap_beyond_structural_stop_emergency_closes():
    broker = FakeBroker()
    broker.force_fill_price = 1.2490  # Below long structural stop 1.2491.
    with pytest.raises(ExecutionRejected, match="no longer below"):
        ExecutionEngine(make_settings(), broker).process(entry_event(event_id="evt-44444444"))
    assert broker.close_calls == 1
    assert broker.positions(symbol="GBPUSD") == []


def test_exit_is_close_only_and_noop_if_broker_already_flat():
    broker = FakeBroker()
    settings = make_settings()
    e = entry_event(
        event_id="evt-exit-0001",
        event_type="EXIT",
        signal_time_ms=int((time.time() - 1000) * 1000),  # stale exits must still be processed
    )
    result = ExecutionEngine(settings, broker).process(e)
    assert result["status"] == "NO_POSITION_NOOP"
    assert broker.open_calls == 0


def test_tv_bracket_exit_is_informational_by_default_broker_protection_is_authoritative():
    broker = FakeBroker()
    settings = make_settings()
    ExecutionEngine(settings, broker).process(entry_event(event_id="evt-open-5555"))
    assert broker.positions(symbol="GBPUSD")
    exit_event = entry_event(event_id="evt-exit-5555", event_type="EXIT")
    result = ExecutionEngine(settings, broker).process(exit_event)
    assert result["status"] == "TV_EXIT_OBSERVED_BROKER_PROTECTION_AUTHORITATIVE"
    assert broker.positions(symbol="GBPUSD")
    assert broker.close_calls == 0


def test_optional_tv_exit_closes_existing_bot_position_without_opening_opposite():
    broker = FakeBroker()
    settings = make_settings(execute_tradingview_exit_alerts=True)
    ExecutionEngine(settings, broker).process(entry_event(event_id="evt-open-6666"))
    exit_event = entry_event(event_id="evt-exit-6666", event_type="EXIT")
    result = ExecutionEngine(settings, broker).process(exit_event)
    assert result["status"] == "POSITIONS_CLOSED"
    assert broker.positions(symbol="GBPUSD") == []
    assert broker.open_calls == 1  # only the original entry


def test_live_mode_remains_locked_without_explicit_live_flag():
    broker = FakeBroker()
    broker.account_snapshot.is_demo = False
    with pytest.raises(ExecutionRejected, match="Live trading is disabled"):
        ExecutionEngine(make_settings(execution_mode="live", live_trading_enabled=False), broker).process(entry_event())


def test_tick_rounding_moves_stop_and_target_outward():
    broker = FakeBroker()
    # Force a coarser executable tick than the quote point to prove quantization.
    broker.symbols["GBPUSD"].tick_size = 0.0001
    result = ExecutionEngine(make_settings(), broker).process(
        entry_event(structural_stop=1.24917, event_id="evt-tick-round")
    )
    assert result["sl"] == pytest.approx(1.2491)
    assert result["tp"] >= 1.2521 - 1e-12


def test_new_entry_can_be_hard_paused():
    broker = FakeBroker()
    with pytest.raises(ExecutionRejected, match="New entries are paused"):
        ExecutionEngine(make_settings(new_entries_enabled=False), broker).process(entry_event())
    assert broker.open_calls == 0


def test_uncertain_entry_is_reconciled_if_position_exists():
    broker = FakeBroker()
    broker.open_result_uncertain = True
    broker.uncertain_creates_position = True
    result = ExecutionEngine(make_settings(reconciliation_wait_seconds=0), broker).process(
        entry_event(event_id="evt-uncertain-found")
    )
    assert result["status"] == "DEMO_ORDER_OPENED"
    assert len(broker.positions(symbol="GBPUSD")) == 1


def test_uncertain_entry_is_not_blindly_retried_when_position_not_found():
    broker = FakeBroker()
    broker.open_result_uncertain = True
    broker.uncertain_creates_position = False
    with pytest.raises(RuntimeError, match="outcome is uncertain"):
        ExecutionEngine(make_settings(reconciliation_wait_seconds=0), broker).process(
            entry_event(event_id="evt-uncertain-missing")
        )
    assert broker.open_calls == 1


def test_account_wide_risk_cap_blocks_second_bot_position():
    broker = FakeBroker()
    settings = make_settings(max_open_positions=5, max_total_risk_pct=1.5)
    ExecutionEngine(settings, broker).process(entry_event(event_id="evt-first-risk"))
    # A second mapped instrument would be required to avoid the same-symbol guard, but the
    # already-open position itself consumes about 1% and the next 1% trade breaches 1.5%.
    broker.symbols["XAUUSD"].bid = 2500.0
    broker.symbols["XAUUSD"].ask = 2500.2
    settings2 = make_settings(
        max_open_positions=5,
        max_total_risk_pct=1.5,
        symbol_map={"TV:GBPUSD": "GBPUSD", "TV:XAUUSD": "XAUUSD"},
    )
    gold = entry_event(
        event_id="evt-second-risk",
        trade_id="L-2",
        ticker="TV:XAUUSD",
        signal_price=2500.2,
        structural_stop=2490.2,
        planned_target=2520.2,
    )
    with pytest.raises(ExecutionRejected, match="total risk cap"):
        ExecutionEngine(settings2, broker).process(gold)


def test_symbol_allowlist_is_enforced():
    broker = FakeBroker()
    e = entry_event(ticker="TV:UNKNOWN", event_id="evt-unknown-1")
    with pytest.raises(ExecutionRejected, match="not mapped"):
        ExecutionEngine(make_settings(), broker).process(e)
