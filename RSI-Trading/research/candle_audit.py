"""Audit closed M5 bars against explicit RSI/pivot settings, without simulating trades."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float


def utc(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def load_candles(path: Path) -> list[Candle]:
    bars = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"time", "open", "high", "low", "close"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires time,open,high,low,close columns")
        for line, row in enumerate(reader, 2):
            try:
                t = int(row["time"])
                o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid numeric value at CSV line {line}") from exc
            if (t <= 0 or t % 300 or not all(math.isfinite(x) and x > 0 for x in (o, h, l, c))
                    or l > min(o, c) or h < max(o, c) or l > h):
                raise ValueError(f"Invalid candle/M5 timestamp at CSV line {line}")
            if bars and t <= bars[-1].time:
                raise ValueError(f"Duplicate or out-of-order timestamp at CSV line {line}")
            bars.append(Candle(t, o, h, l, c))
    if not bars:
        raise ValueError("CSV contains no candles")
    return bars


def prices(bars: list[Candle], source: str) -> list[float]:
    if source in {"open", "high", "low", "close"}:
        return [getattr(b, source) for b in bars]
    if source == "hl2":
        return [(b.high + b.low) / 2 for b in bars]
    if source == "hlc3":
        return [(b.high + b.low + b.close) / 3 for b in bars]
    if source == "ohlc4":
        return [(b.open + b.high + b.low + b.close) / 4 for b in bars]
    raise ValueError("Unsupported price source")


def wilder_rsi(values: list[float], length: int) -> list[float | None]:
    if length < 2:
        raise ValueError("RSI length must be >= 2")
    output: list[float | None] = [None] * len(values)
    if len(values) <= length:
        return output
    deltas = [b - a for a, b in zip(values, values[1:])]
    up = sum(max(d, 0) for d in deltas[:length]) / length
    down = sum(max(-d, 0) for d in deltas[:length]) / length
    for i in range(length, len(values)):
        if i > length:
            d = deltas[i - 1]
            up += (max(d, 0) - up) / length
            down += (max(-d, 0) - down) / length
        # A completely flat seed is treated conservatively as unavailable.
        output[i] = None if up == down == 0 else 100 if down == 0 else 0 if up == 0 else 100 * up / (up + down)
    return output


def confirmed_states(bars: list[Candle], swing: int, ties: str = "latest") -> tuple[list[str], dict]:
    if not 1 <= swing <= 20 or ties not in {"latest", "strict"}:
        raise ValueError("Swing bars must be 1..20 and tie policy latest or strict")
    last_h = prev_h = last_l = prev_l = None
    epoch = -1
    state = "UNKNOWN"
    states = []
    gaps = breaks = 0

    def pivot(i: int, key: str, high: bool) -> float | None:
        origin = i - swing
        if origin < swing:
            return None
        value = getattr(bars[origin], key)
        for j in range(origin - swing, i + 1):
            if j == origin:
                continue
            other = getattr(bars[j], key)
            strict = ties == "strict" or j > origin
            rejected = (value <= other if strict else value < other) if high else (value >= other if strict else value > other)
            if rejected:
                return None
        return value

    for i, b in enumerate(bars):
        gap = i > 0 and b.time - bars[i - 1].time > 300
        broken = (state == "BULLISH" and b.close < last_l) or (state == "BEARISH" and b.close > last_h)
        if gap or broken:
            gaps += int(gap)
            breaks += int(broken)
            last_h = prev_h = last_l = prev_l = None
            epoch = i
        if i - swing > epoch:
            high, low = pivot(i, "high", True), pivot(i, "low", False)
            if high is not None:
                prev_h, last_h = last_h, high
            if low is not None:
                prev_l, last_l = last_l, low
        if None in (prev_h, last_h, prev_l, last_l):
            state = "UNKNOWN"
        elif last_h > prev_h and last_l > prev_l:
            state = "BULLISH"
        elif last_h < prev_h and last_l < prev_l:
            state = "BEARISH"
        else:
            state = "RANGE"
        states.append(state)
    return states, {"gap_resets": gaps, "structure_break_resets": breaks}


def audit(path: Path, *, rsi_length: int, source: str, swing_bars: int, ties: str = "latest") -> dict:
    bars = load_candles(path)
    rsi = wilder_rsi(prices(bars, source), rsi_length)
    states, resets = confirmed_states(bars, swing_bars, ties)
    gates: Counter = Counter()
    extremes: Counter = Counter()
    by_state: Counter = Counter()
    candidates = []
    minimum = maximum = None
    for b, r, state in zip(bars, rsi, states):
        if r is not None:
            if r < 15 or r > 85:
                key = "below_15" if r < 15 else "above_85"
                extremes[key] += 1
                by_state[key + ":" + state] += 1
            if state == "BULLISH" and (minimum is None or r < minimum):
                minimum = r
            if state == "BEARISH" and (maximum is None or r > maximum):
                maximum = r
        qualifies = r is not None and ((state == "BULLISH" and r < 15) or (state == "BEARISH" and r > 85))
        gate = "unknown" if state == "UNKNOWN" or r is None else "range" if state == "RANGE" else "candidate" if qualifies else "rsi"
        gates[gate] += 1
        if qualifies:
            candidates.append({"bar_open_time_utc": utc(b.time), "decision_time_utc": utc(b.time + 300),
                               "side": "LONG" if state == "BULLISH" else "SHORT", "rsi": r, "close": b.close})
    return {
        "scope": "Entry-condition audit only; no position/latch/sizing/fill/cost or P&L simulation; native Pine parity unverified",
        "input": {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "rows": len(bars), "first_bar_open_utc": utc(bars[0].time), "last_bar_open_utc": utc(bars[-1].time),
                  "timestamp_interpretation": "Exported Unix seconds, interpreted as UTC without shifting"},
        "settings": {"rsi_length": rsi_length, "source": source, "swing_bars": swing_bars, "pivot_tie_policy": ties,
                     "rsi_smoothing": "Wilder RMA seeded from first length close/source changes",
                     "flat_seed_policy": "Unavailable until movement; native flat-seed behavior not claimed",
                     "buy_below": 15, "sell_above": 85, "structure_reset": "Close break or gap >300 seconds"},
        "states": dict(Counter(states)), "gates": dict(gates), "resets": resets,
        "gap_seconds": dict(Counter(b.time - a.time for a, b in zip(bars, bars[1:]) if b.time - a.time > 300)),
        "extremes": {"below_15": extremes["below_15"], "above_85": extremes["above_85"], "by_state": dict(by_state)},
        "bullish_min_rsi": minimum, "bearish_max_rsi": maximum,
        "qualifying_bars": len(candidates), "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--rsi-length", type=int, required=True)
    parser.add_argument("--source", choices=["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"], required=True)
    parser.add_argument("--swing-bars", type=int, required=True)
    parser.add_argument("--ties", choices=["latest", "strict"], default="latest")
    args = parser.parse_args()
    try:
        result = audit(args.csv, rsi_length=args.rsi_length, source=args.source, swing_bars=args.swing_bars, ties=args.ties)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Audit failed: {exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
