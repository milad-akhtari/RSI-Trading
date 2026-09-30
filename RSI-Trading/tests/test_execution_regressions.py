from dataclasses import replace
import math
import time

import pytest

from automation.engine import ExecutionEngine, ExecutionRejected
from automation.models import WebhookEvent
from tests.fakes import FakeBroker
from tests.test_execution_engine import entry_event, make_settings


def test_late_exit_cannot_close_newer_trade():
    broker = FakeBroker()
    settings = make_settings(execute_tradingview_exit_alerts=True)
    engine = ExecutionEngine(settings, broker)
    engine.process(entry_event(trade_id="new-trade"))
    result = engine.process(entry_event(event_type="EXIT", trade_id="old-trade", event_id="exit-old-trade"))
    assert result["status"] == "NO_MATCHING_TRADE_NOOP"
    assert broker.close_calls == 0 and len(broker.positions()) == 1


def test_other_instance_exit_cannot_close_position():
    broker = FakeBroker()
    engine = ExecutionEngine(make_settings(execute_tradingview_exit_alerts=True), broker)
    engine.process(entry_event(instance_id="chart-a"))
    result = engine.process(entry_event(instance_id="chart-b", event_type="EXIT", event_id="exit-chart-b"))
    assert result["status"] == "NO_MATCHING_TRADE_NOOP"
    assert broker.close_calls == 0


@pytest.mark.parametrize("override", [{"mt5_login": 200000}, {"mt5_server": "Other-Demo"}, {"mt5_login": None}])
def test_account_identity_is_pinned_before_submission(override):
    broker = FakeBroker()
    with pytest.raises(ExecutionRejected, match="MT5_LOGIN|MT5_SERVER"):
        ExecutionEngine(make_settings(**override), broker).process(entry_event())
    assert broker.open_calls == 0


def test_future_entry_and_stale_quote_are_rejected():
    broker = FakeBroker()
    engine = ExecutionEngine(make_settings(), broker)
    with pytest.raises(ExecutionRejected, match="future"):
        engine.process(entry_event(signal_time_ms=int((time.time() + 600) * 1000)))
    broker.symbols["GBPUSD"].quote_time_ms = int((time.time() - 600) * 1000)
    with pytest.raises(ExecutionRejected, match="quote is stale"):
        engine.process(entry_event())
    assert broker.open_calls == 0


@pytest.mark.parametrize("field,value", [("bid", math.nan), ("ask", math.inf), ("volume_step", 0), ("tick_size", 0)])
def test_invalid_broker_metadata_cannot_size_or_submit(field, value):
    broker = FakeBroker()
    setattr(broker.symbols["GBPUSD"], field, value)
    with pytest.raises(ExecutionRejected, match="metadata"):
        ExecutionEngine(make_settings(), broker).process(entry_event())
    assert broker.open_calls == 0


def test_positive_but_wrong_protection_is_not_accepted():
    broker = FakeBroker()
    original = broker.set_protection
    def wrong_protection(**kw):
        result = original(**kw)
        broker._positions[0] = replace(broker._positions[0], sl=kw["sl"] - 0.01)
        return result
    broker.set_protection = wrong_protection
    with pytest.raises(RuntimeError, match="protection could not be confirmed"):
        ExecutionEngine(make_settings(), broker).process(entry_event())
    assert broker.close_calls == 1 and not broker.positions()


def test_partial_emergency_close_remains_an_unresolved_error():
    broker = FakeBroker()
    broker.protection_result_ok = False
    original = broker.close_position
    def partial_close(**kw):
        position = kw["position"]
        result = original(**kw)
        broker._positions.append(replace(position, volume=position.volume / 2))
        return result
    broker.close_position = partial_close
    with pytest.raises(RuntimeError, match="DID NOT REMOVE POSITION"):
        ExecutionEngine(make_settings(reconciliation_wait_seconds=0), broker).process(entry_event())
    assert len(broker.positions()) == 1


def test_volume_max_is_still_rounded_to_step():
    broker = FakeBroker()
    broker.symbols["GBPUSD"].volume_max = 0.955
    result = ExecutionEngine(make_settings(), broker).process(entry_event())
    assert result["volume"] == pytest.approx(0.95)


def test_actual_fill_target_and_risk_are_not_taken_from_signal_close():
    broker = FakeBroker()
    broker.force_fill_price = 1.25008
    result = ExecutionEngine(make_settings(), broker).process(entry_event())
    assert result["fill"] == pytest.approx(1.25008)
    assert result["tp"] == pytest.approx(1.25204)


def test_schema_tick_rounding_rejects_inward_or_excessive_target():
    event = entry_event()
    payload = event.model_dump(mode="json")
    payload.update(schema_version="1.1", chart_tick_size=0.0001)
    payload["planned_target"] = 1.2522
    assert WebhookEvent.model_validate(payload).planned_target == pytest.approx(1.2522)
    for target in [1.2520, 1.2524]:
        payload["planned_target"] = target
        with pytest.raises(ValueError, match="2R bracket"):
            WebhookEvent.model_validate(payload)


@pytest.mark.parametrize("field", ["risk_pct", "signal_price", "planned_target", "chart_tick_size"])
def test_nonfinite_payload_fields_are_rejected(field):
    payload = entry_event().model_dump(mode="json")
    payload[field] = math.nan
    with pytest.raises(ValueError):
        WebhookEvent.model_validate(payload)


@pytest.mark.parametrize("rsi", [14.99, 15, 15.01, 19.99, 20, 50, 80, 80.01, 84.99, 85, 85.01, 90, 90.01])
@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_actual_gateway_schema_obeys_every_rsi_boundary(side, rsi):
    kwargs = dict(side=side, rsi=rsi, market_state="BULLISH" if side == "LONG" else "BEARISH")
    if side == "SHORT":
        kwargs["structural_stop"] = 1.2511
    eligible = rsi < 15 if side == "LONG" else rsi > 85
    if eligible:
        assert entry_event(**kwargs).side.value == side
    else:
        with pytest.raises(ValueError):
            entry_event(**kwargs)
