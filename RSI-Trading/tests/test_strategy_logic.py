import pytest

from .helpers_strategy import BEARISH, BULLISH, RANGE, UNKNOWN, ExtremeLatch, bracket, eligibility, market_state


@pytest.mark.parametrize(
    "prev_h,last_h,prev_l,last_l,expected",
    [
        (100, 110, 90, 95, BULLISH),
        (110, 100, 95, 90, BEARISH),
        (100, 110, 95, 90, RANGE),
        (110, 100, 90, 95, RANGE),
        (100, 100, 90, 95, RANGE),
        (None, 100, 90, 95, UNKNOWN),
    ],
)
def test_market_state(prev_h, last_h, prev_l, last_l, expected):
    assert market_state(prev_h, last_h, prev_l, last_l) == expected


def test_pullback_does_not_reverse_structure_without_confirmed_structural_break():
    # Price/candle direction is deliberately absent from the structural state function.
    # A bearish pullback inside HH/HL structure therefore remains BULLISH.
    assert market_state(100, 110, 90, 95) == BULLISH


@pytest.mark.parametrize(
    "rsi,buy,sell",
    [
        (14.99, True, False),
        (15, False, False),
        (15.01, False, False),
        (19.99, False, False),
        (20, False, False),
        (50, False, False),
        (80, False, False),
        (80.01, False, False),
        (84.99, False, False),
        (85, False, False),
        (85.01, False, True),
        (90, False, True),
        (90.01, False, True),
    ],
)
def test_exact_rsi_boundaries(rsi, buy, sell):
    assert eligibility(BULLISH, rsi)[0] is buy
    assert eligibility(BEARISH, rsi)[1] is sell


@pytest.mark.parametrize("state", [RANGE, UNKNOWN])
def test_range_and_unknown_block(state):
    for rsi in (0, 14.99, 85.01, 100):
        assert eligibility(state, rsi) == (False, False)


def test_fixed_two_r_long_and_short():
    assert bracket("LONG", 100, 95) == (95, 110)
    assert bracket("SHORT", 100, 105) == (105, 90)


def test_persistent_extreme_requires_reset_before_reentry():
    latch = ExtremeLatch()
    latch.update(14)
    assert latch.long_armed
    latch.consume_long()
    assert not latch.long_armed
    latch.update(10)
    assert not latch.long_armed
    latch.update(15)
    assert latch.long_armed
