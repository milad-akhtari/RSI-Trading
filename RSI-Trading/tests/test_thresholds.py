import pytest


def classify(trend: str, rsi: float):
    buy = trend == "BULLISH" and rsi < 15
    sell = trend == "BEARISH" and rsi > 85
    stronger_sell = sell and rsi > 90
    stronger_buy = buy  # lower values are qualitatively stronger; no extra cutoff approved
    return buy, sell, stronger_buy, stronger_sell


@pytest.mark.parametrize("rsi,eligible", [
    (14.99, True), (15, False), (15.01, False), (19.99, False),
    (20, False), (50, False), (80, False), (80.01, False),
    (84.99, False), (85, False), (85.01, False), (90, False), (90.01, False),
])
def test_buy_thresholds(rsi, eligible):
    assert classify("BULLISH", rsi)[0] is eligible


@pytest.mark.parametrize("rsi,eligible,stronger", [
    (14.99, False, False), (15, False, False), (15.01, False, False),
    (19.99, False, False), (20, False, False), (50, False, False),
    (80, False, False), (80.01, False, False), (84.99, False, False),
    (85, False, False), (85.01, True, False), (90, True, False), (90.01, True, True),
])
def test_sell_thresholds(rsi, eligible, stronger):
    _, sell, _, strong = classify("BEARISH", rsi)
    assert sell is eligible
    assert strong is stronger


def test_range_and_unknown_block_entries():
    for trend in ("RANGE", "UNKNOWN"):
        for rsi in (0, 14.99, 85.01, 100):
            buy, sell, *_ = classify(trend, rsi)
            assert not buy and not sell
