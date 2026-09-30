# RSI strategy historical test

Run on September 30, 2026. Current Pine source: v1.5.

**Result: no qualifying entries in either supplied sample.** Starting flat, this implies no orders, positions or closed trades for the current rules. Win rate and profit factor cannot be calculated.

## Results

| Market | M5 bars | RSI below 15 | RSI above 85 | Qualifying BUY | Qualifying SELL | Trades implied |
|---|---:|---:|---:|---:|---:|---:|
| US30 | 20,000 | 150 | 121 | 0 | 0 | 0 |
| GBPUSD | 20,000 | 58 | 94 | 0 | 0 | 0 |

| Accounting metric | US30 | GBPUSD |
|---|---:|---:|
| Initial simulated cash | $10,000 | $10,000 |
| Ending cash with no entries | $10,000 | $10,000 |
| Trade-related profit/loss | $0 | $0 |
| Return from trades | 0% | 0% |
| Win rate | Unavailable | Unavailable |
| Profit factor | Unavailable | Unavailable |

The $10,000 starting cash is the Pine simulation setting, not the balance of the Windows demo account. Flat cash and zero profit result from inactivity; they do not establish trading performance. No sizing, commission, spread, slippage, bracket fill, margin or protective-exit path was exercised.

## Rules replayed

- Closed standard M5 OHLC bars; RSI 9 on Close with Wilder smoothing. The separate SMA 14 is not an entry condition.
- Confirmed swing pivots with two bars left and two right. A pivot becomes available at its confirmation bar.
- Bullish: higher highs and higher lows. Bearish: lower lows and lower highs.
- BUY requires bullish structure and RSI strictly below 15. SELL requires bearish structure and RSI strictly above 85.
- A confirmed supporting-swing close break or a gap over 300 seconds resets structure. Fresh pivots must originate after the reset.
- Range and unknown structure block entries. Starting positions are empty.
- The current strategy also has a one-position limit, extreme latch, structural stop, 1% risk and 2R target. Those later stages cannot create a trade when no initial entry pair qualifies.

## Why there were no trades

| US30 extreme | Unknown structure | Bearish | Bullish | Range | Required trend matches |
|---|---:|---:|---:|---:|---:|
| RSI below 15 | 76 | 66 | 0 | 8 | 0 bullish |
| RSI above 85 | 37 | 0 | 63 | 21 | 0 bearish |

US30's lowest RSI while the replay state remained bullish was 18.8369, above the BUY threshold. Its highest RSI while bearish was 82.5867, below the SELL threshold. Thus the mismatch occurs before quantity, margin or order execution.

These results show no tradable examples under the implemented structure rules in the supplied history. They do not demonstrate that the implementation reproduces every previous manual trend selection, nor establish a profitable strategy. Parameters and thresholds were not optimized to generate trades.

## Coverage and verification

| Input | First exported bar | Last exported bar |
|---|---|---|
| US30_M5_history.csv | 2026-06-18T14:50:00+00:00 | 2026-09-30T05:30:00+00:00 |
| GBPUSD_M5_history.csv | 2026-06-24T18:35:00+00:00 | 2026-09-30T05:10:00+00:00 |

Dates above are literal Unix-to-UTC interpretations of the exported timestamps. The historical broker clock offset is not independently verified. The later photographed candle is not included in these exports. The files are the MT5 broker history, not Capital.com TradingView chart history.

All 20,000 rows per file passed finite positive OHLC, M5 timestamp-grid, ordering and duplicate checks. A separately written JavaScript calculation agreed with the Python replay on every bar’s trend state. The maximum RSI difference was below 0.000000001. Alternate strict pivot ties also produced zero qualifying pairs on both samples. Source files were unchanged.

This is a local historical entry replay with zero-trade accounting. It is not a TradingView Strategy Tester execution or a validated emulation of that platform’s fills. The result ends at the zero-entry gate, so trade-performance and fill-accuracy claims are unavailable. [TradingView’s strategy documentation](https://www.tradingview.com/pine-script-docs/concepts/strategies/) describes its separate broker emulator and strategy report.

## Reproduction

Run from the supplied project with each CSV available at the given path:

```text
python -m research.candle_audit research/fixtures/US30_M5_history.csv --rsi-length 9 --source close --swing-bars 2
python -m research.candle_audit research/fixtures/GBPUSD_M5_history.csv --rsi-length 9 --source close --swing-bars 2
```

The bundled audit emits entry-condition statistics, not fill/P&L simulation. The no-trade accounting above follows from zero candidates, not an executed fill model.

Source identity:

- `US30_M5_history.csv` SHA-256: `b51c9378c36a46ec7b2a3930df96dcec9df6d997c28a2dfb48deab403d089ccf`
- `GBPUSD_M5_history.csv` SHA-256: `7b796c0f2f49819d719e3cd18e6d9f4d6b7b86b34714fc267b6f4e9eb78d0240`
- Pine source SHA-256: `0358f8c6e8aa148fddfcb336a4175483d515f425c91c052685509c452e7e4fb1`
- Source commit: `bdd76f9c473fae4031ebf390b956dc1f6db85c87`
