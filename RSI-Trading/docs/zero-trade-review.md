# Review request: why no qualifying trades?

Start here when reviewing this project. The current implementation produces **zero qualifying entry pairs** on the supplied 20,000-bar US30 and 20,000-bar GBPUSD samples. This occurs before order sizing, margin checks or MT5 execution. Changing the gateway cannot create the missing entry pairs.

## Read these files first

1. [Historical replay report](RSI_Backtest_Report.md): counts, limitations and tested source identity.
2. [Strategy specification](strategy-spec.md): the exact translation of the manual rules.
3. [Pine source](../pine/rsi_trend_strategy.pine): confirmed swing updates, structure resets and raw entry conditions.
4. [Python replay](../research/candle_audit.py): an executable entry-condition audit.
5. [Selected TradingView candle](evidence/tradingview-selected-candle.json): native chart observation.

## Confirmed rules versus implementation choices

| Rule | Status |
|---|---|
| Standard M5 only; no other timeframe confirmation | User confirmed |
| RSI 9 on Close; separate SMA 14 is display smoothing | Observed in the user's TradingView settings |
| Bullish higher highs + higher lows; bearish lower lows + lower highs | User confirmed |
| BUY only bullish and RSI < 15; SELL only bearish and RSI > 85 | User confirmed |
| Range: no entry; target 2R | User confirmed |
| Skip BUY after an M5 close below the latest supporting higher low | User explicitly confirmed |
| Two left/two right bars to confirm a swing | Engineering default; manual swing selection has not been matched |
| Symmetric bearish close-break rule | Engineering default; not separately confirmed |
| Clear all swings on a structure break or gap longer than 300 seconds | Engineering choice |
| Require two fresh highs and two fresh lows originating after a reset | Engineering choice |
| Equal/conflicting swings become range; insufficient swings become unknown | Engineering choice |

The user authorized completing the software with the available information. That does not establish equivalence with their earlier discretionary trend selection.

## Evidence to investigate

US30 has 150 bars below RSI 15 and 121 above RSI 85. None of the low-RSI bars are bullish; none of the high-RSI bars are bearish under the current structure definition. Its minimum bullish RSI is 18.8369 and maximum bearish RSI is 82.5867.

On the photographed Capital.com US30 M5 candle opening September 30, 2026 at 11:15 UTC, built-in RSI reads 9.26 and the strategy's rounded decision RSI reads 9.3. The strategy state is BEARISH, so there is no BUY candidate. This observation supports RSI agreement at that candle; it does not prove full indicator or trend parity.

Please review whether the chosen 2/2 pivots represent the user's intended last trend, whether resetting all pivots/requiring fresh pivots makes structure unavailable during the intended dip, and whether the Python and Pine update order agree. Treat any proposed alternative as a clearly documented strategy change. Do not relax thresholds or remove the confirmed bullish close-break rule just to generate entries.

## Reproduce without MT5 or credentials

From the repository root, use Python 3.12 or later:

```bash
python -m research.candle_audit research/fixtures/US30_M5_history.csv --rsi-length 9 --source close --swing-bars 2
python -m research.candle_audit research/fixtures/GBPUSD_M5_history.csv --rsi-length 9 --source close --swing-bars 2
```

Expected: 20,000 bars and zero entry candidates for each. Compare with the saved `docs/evidence/*_RSI9_audit.json` results; input paths may differ, but hashes and counts should agree.

The fixtures contain broker OHLC, tick volume and spread only. Their timestamps are literal exported Unix timestamps; the historical broker clock offset is not independently verified. They are MT5 broker data, not Capital.com TradingView candles. The later photographed candle is outside these exports.

Application checks:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -o addopts='' -q
```

The tested software snapshot had 230 passing tests. These include logic, static Pine contracts and fake-broker execution checks; they do not validate native TradingView fills or real MT5 orders. Pine v1.4 compilation/selected-candle diagnostics were observed; v1.5 adds diagnostic display changes and still needs native compile/display verification.

This replay is not a fill/P&L backtest. With no entries, win rate and profit factor are unavailable. Order submission remains disabled. Share proposed fixes through a separate branch for review.
