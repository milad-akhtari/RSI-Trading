import pytest

from research.candle_audit import Candle, audit, confirmed_states, load_candles, wilder_rsi


def structure_bars():
    highs = [10, 12, 15, 12, 11, 14, 16, 14, 13, 15, 17, 15, 14, 16, 18]
    lows = [8, 9, 10, 9, 8, 10, 11, 10, 9, 11, 12, 11, 10, 12, 13]
    return [Candle(300 * (i + 1), (h + l) / 2, h, l, (h + l) / 2) for i, (h, l) in enumerate(zip(highs, lows))]


def test_wilder_seed_and_recursive_update_with_known_changes():
    values = wilder_rsi([10, 11, 12, 11, 13], 3)
    assert values[:3] == [None, None, None]
    assert values[3] == pytest.approx(100 * 2 / 3)
    # Seed gains 2/3, losses 1/3, then gain 2: gains 10/9, losses 2/9.
    assert values[4] == pytest.approx(100 * 10 / 12)


def test_flat_seed_is_unavailable_and_cannot_create_extreme_signal():
    assert wilder_rsi([10] * 20, 14) == [None] * 20
    assert wilder_rsi([10] * 15 + [11], 14)[-1] == 100


def test_pivots_are_only_usable_after_confirmation_and_future_bars_do_not_rewrite_history():
    bars = structure_bars()
    states, _ = confirmed_states(bars, 2)
    assert states[9] == "UNKNOWN"
    assert states[10] == "BULLISH"
    prefix, _ = confirmed_states(bars[:11], 2)
    assert prefix == states[:11]
    future = bars[:11] + [Candle(b.time, 30, 40, 1, 30) for b in bars[11:]]
    changed, _ = confirmed_states(future, 2)
    assert changed[:11] == prefix


def test_close_break_clears_structure_and_excludes_pre_break_pivots():
    bars = structure_bars()
    bars[11] = Candle(bars[11].time, 10, 15, 7, 8)
    states, resets = confirmed_states(bars, 2)
    assert states[10] == "BULLISH"
    assert states[11:14] == ["UNKNOWN"] * 3
    assert resets["structure_break_resets"] == 1


def test_gap_clears_structure_before_any_old_pivot_can_restore_it():
    bars = structure_bars()
    bars[11:] = [Candle(b.time + 3600, b.open, b.high, b.low, b.close) for b in bars[11:]]
    states, resets = confirmed_states(bars, 2)
    assert states[10] == "BULLISH"
    assert states[11:] == ["UNKNOWN"] * 4
    assert resets["gap_resets"] == 1


@pytest.mark.parametrize("row", [
    "300,10,9,8,10", "300,10,12,11,10", "301,10,12,8,10",
    "300,10,nan,8,10", "300,10,inf,8,10", "300,10,12,0,10",
])
def test_invalid_data_is_rejected_instead_of_reported_as_zero_signals(tmp_path, row):
    file = tmp_path / "input.csv"
    file.write_text("time,open,high,low,close\n" + row)
    with pytest.raises(ValueError, match="Invalid candle"):
        load_candles(file)


@pytest.mark.parametrize("times", ["300,300", "600,300"])
def test_duplicate_and_out_of_order_rows_are_rejected(tmp_path, times):
    file = tmp_path / "input.csv"
    file.write_text("time,open,high,low,close\n" + "\n".join(f"{t},10,12,8,10" for t in times.split(',')))
    with pytest.raises(ValueError, match="timestamp"):
        load_candles(file)


def test_empty_data_is_rejected(tmp_path):
    file = tmp_path / "input.csv"
    file.write_text("time,open,high,low,close\n")
    with pytest.raises(ValueError, match="no candles"):
        load_candles(file)


def test_report_accounts_for_all_bars_and_discloses_scope(tmp_path):
    file = tmp_path / "input.csv"
    file.write_text("time,open,high,low,close\n" + "\n".join(
        f"{b.time},{b.open},{b.high},{b.low},{b.close}" for b in structure_bars()))
    result = audit(file, rsi_length=3, source="close", swing_bars=2)
    assert sum(result["states"].values()) == sum(result["gates"].values()) == 15
    assert result["qualifying_bars"] == len(result["candidates"])
    assert len(result["input"]["sha256"]) == 64
    assert "no position/latch/sizing/fill/cost or P&L" in result["scope"]
