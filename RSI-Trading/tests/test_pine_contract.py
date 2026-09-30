from pathlib import Path


PINE = (Path(__file__).resolve().parents[1] / "pine" / "rsi_trend_strategy.pine").read_text(encoding="utf-8")


def test_pine_is_v6_strategy_not_indicator():
    assert "//@version=6" in PINE
    assert "strategy(" in PINE
    assert "indicator(" not in PINE


def test_pine_enforces_standard_m5_chart_without_mtf_signal_requests():
    assert "chart.is_standard" in PINE
    assert "timeframe.isminutes and timeframe.multiplier == 5" in PINE
    assert "request.security" not in PINE
    assert "request.security_lower_tf" not in PINE


def test_pine_preserves_strict_rsi_thresholds():
    assert "marketState == STATE_BULLISH and rsi < 15" in PINE
    assert "marketState == STATE_BEARISH and rsi > 85" in PINE
    assert 'signalRsi > 90' in PINE
    assert "rsi <= 15" not in PINE
    assert "rsi >= 85" not in PINE


def test_pine_does_not_use_indicator_only_alertcondition_or_extra_alert_stream():
    assert "alertcondition(" not in PINE
    assert "alert(" not in PINE
    assert "{{strategy.order.alert_message}}" in PINE


def test_pine_fill_recalculations_cannot_generate_entries():
    assert "barstate.isconfirmed" in PINE
    assert "calc_on_every_tick = false" in PINE
    assert "calc_on_order_fills = true" in PINE
    assert "process_orders_on_close = true" in PINE
    assert "barstate.isconfirmed and not fillRecalculation" in PINE
    assert "bool enterLong = evaluateSignal" in PINE
    assert "bool enterShort = evaluateSignal" in PINE


def test_pine_has_no_implicit_pyramiding_or_reversal_helpers():
    assert "pyramiding = 0" in PINE
    assert "strategy.close_all" not in PINE
    # A close-only rescue for invalid fill risk is allowed; it is not a trend/RSI exit.
    assert 'comment = "Invalid fill risk"' in PINE


def test_pine_payload_contract_contains_execution_identifiers():
    for token in (
        '"schema_version"',
        '"strategy"',
        '"instance_id"',
        '"event_id"',
        '"event_type"',
        '"ticker"',
        '"timeframe"',
        '"signal_time_ms"',
        '"structural_stop"',
        '"planned_target"',
        '"trade_id"',
    ):
        assert token in PINE


def test_pine_target_uses_fill_and_keeps_frozen_stop():
    assert "activeFill := strategy.position_avg_price" in PINE
    assert "activeTarget := f_target(activeSide, activeFill, activeStop)" in PINE
    assert "strategy.convert_to_account" in PINE
    assert "linearContractVerified = input.bool(false" in PINE
    assert "input.source" not in PINE  # no other indicator / MTF source can be imported


def test_pine_stable_event_identity_includes_instance_and_bar_time():
    assert '"rsi-trend|" + instanceIdInput' in PINE
    assert 'str.tostring(time_close)' in PINE
    assert "sequence" not in PINE


def test_pine_invalidation_and_gap_require_fresh_structure():
    assert "close < lastLow" in PINE and "close > lastHigh" in PINE
    assert "structureEpoch := bar_index" in PINE
    assert "bar_index - swingBars > structureEpoch" in PINE
