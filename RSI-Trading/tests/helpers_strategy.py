from __future__ import annotations

from dataclasses import dataclass


UNKNOWN = 0
BULLISH = 1
BEARISH = -1
RANGE = 2


def market_state(prev_high: float | None, last_high: float | None, prev_low: float | None, last_low: float | None) -> int:
    if None in (prev_high, last_high, prev_low, last_low):
        return UNKNOWN
    if last_high > prev_high and last_low > prev_low:
        return BULLISH
    if last_high < prev_high and last_low < prev_low:
        return BEARISH
    return RANGE


def eligibility(state: int, rsi: float) -> tuple[bool, bool]:
    return state == BULLISH and rsi < 15, state == BEARISH and rsi > 85


def bracket(side: str, entry: float, structural_stop: float, rr: float = 2.0) -> tuple[float, float]:
    if side == "LONG":
        assert structural_stop < entry
        risk = entry - structural_stop
        return structural_stop, entry + rr * risk
    assert structural_stop > entry
    risk = structural_stop - entry
    return structural_stop, entry - rr * risk


@dataclass
class ExtremeLatch:
    long_armed: bool = True
    short_armed: bool = True

    def update(self, rsi: float) -> None:
        if rsi >= 15:
            self.long_armed = True
        if rsi <= 85:
            self.short_armed = True

    def consume_long(self) -> None:
        self.long_armed = False

    def consume_short(self) -> None:
        self.short_armed = False
