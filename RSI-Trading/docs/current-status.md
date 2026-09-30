# Verified progress and remaining checks

Updated 2026-09-30, user local date (America/Los_Angeles). Status is evidence-based;
an implemented safeguard is not represented as a native broker test.

## Verified so far

| Component | Evidence / result |
|---|---|
| Pine v1.2 compilation and diagnostics | User screenshots show standard M5 on GBPUSD and `CAPITALCOM:US30`; both panels appear |
| Wrong timeframe | Earlier user screenshot shows 1m BLOCKED; return to M5 shows M5 OK |
| Windows runtime | Python 3.13.3; native MetaTrader5 package 5.0.6231 connected successfully |
| MT5 account connection | Read-only diagnostic confirms demo, USD equity/free margin 1,000 and account trade/expert permissions; screenshot shows no positions |
| GBPUSD contract | Broker lot size 100,000 GBP; minimum/step 0.01 lot; maximum 500; tick 0.00001; baseline account leverage 100x |
| US30 contract | Exact broker name `US30`, non-custom, contract size 1, minimum/step 0.1 lot, maximum 250, tick 0.01, tick profit/loss value USD 0.01; profit and margin USD |
| TradingView US30 feed | `CAPITALCOM:US30`: point value 1, minimum quantity 0.1, USD, chart tick 0.1; simulation inputs corrected to step/min/max 0.1 / 0.1 / 250, override 0 |
| Local gateway health | User screenshot: ok true, demo, demo submission false, live false, new entries false, reconciliation pause false |
| Local authenticated receipt/deduplication | Same placeholder event accepted twice; first duplicate false, second true, same event ID |
| Updated Windows source files | First update copied 15 files and clock fix copied 8 files; both show zero failures, settings/environment/data excluded |
| Native US30 initial rejection | Uncorrected future quote rejected; broker writes blocked |
| Native quote clock diagnostic | Computer UTC 03:57:37.433437 vs raw tick interpreted UTC 06:57:35.170 on Sep 30; age -10,797.74 seconds, consistent with +3h feed offset |
| Native US30 LONG / SHORT sizing | Both DRY_RUN_DEMO with temporary +10,800s clock setting bound to MetaQuotes-Demo: 0.1 lot, USD 10 risk (1%), USD 25.78 margin; no orders/settings changes |
| Windows gateway worker | Normal worker startup logged rejection of the prior EXAMPLE:GBPUSD placeholder as unmapped |
| Windows entry pause and saved status | Fresh mapped FX:GBPUSD synthetic event accepted then FAILED with attempts 1 and NEW_ENTRIES_ENABLED=false reason; authenticated status re-read retained identical result after requested restart (restart terminal not pictured) |
| User-confirmed RSI setup | New supplied screenshot: RSI 9 Close, separate SMA 14, chart timeframe, divergence off, wait for timeframe closes enabled. Supersedes the earlier 14-period assumption |
| RSI correction on chart | User screenshot shows existing v1.2 strategy changed to 9 Close on CAPITALCOM:US30 M5; separate RSI also shows 9 Close |
| Trend definition / bullish break | User confirmed HH+HL bullish, LL+LH bearish, and skip BUY after M5 close below latest higher low |
| Pine v1.4 historical diagnostics | User screenshots verify US30 M5 compilation and Data Window decision plots |
| Selected historical candle | Sep 30 11:15 UTC: built-in RSI 9.26, strategy rounded RSI 9.3, BEARISH (-1), pairing 0; bullish requirement blocks BUY |
| Final v1.5 display / Windows convenience | Frozen pre-order reason, last-closed RSI and UTC decision time; copy/check launchers implemented. Native display/launcher verification pending |
| Isolated US30 HTTP-to-worker tool | Implemented and fake-broker checks pass; native Windows run pending |
| Automated checks | 230 passed locally, one dependency deprecation warning; fake broker/module only |

TradingView's chart tick (0.1) and MT5's executable tick (0.01) differ for US30.
This is recorded rather than hidden. The execution engine uses broker increments.
Broker and TradingView feeds are separate; contract/feed equivalence and prices
must be reviewed before automation. The simulation quantity limits model the
selected demo contract, not Capital.com's independently verified trading limits.
Forex account leverage must not be assumed to establish US30's margin model.
Native `order_calc_profit()` sizing and `order_calc_margin()` have now been
exercised for both synthetic US30 sides on the selected demo contract. The USD
25.78 margin is a snapshot at the observed price/account state, not a fixed
guarantee for future orders. The gateway's saved clock configuration remains
zero: the +3h exception was passed only to the separate read-only commands.
Native execution and signal correctness remain unverified. Detailed observations:
[Windows/native test record](evidence/windows-native-checks.json).

## Uploaded candle audits

The user exported up to 20,000 bars using MT5 `copy_rates_from_pos(..., 1, 20000)`;
position 1 excludes the current incomplete bar. Files are not modified. Parsed
timestamps are Unix seconds interpreted as UTC, without shifting or aligning
different feeds. Each file has 20,000 positive finite valid OHLC rows, ordered
unique timestamps, and all opens on the M5 timestamp grid.

The later live-quote diagnostic revealed an apparent +3h offset on this demo
server. Therefore exported dates below are literal Unix-to-UTC interpretations,
not independently verified absolute UTC bar times. The historical server clock
must be established before aligning these candles with TradingView or a trade
example. Source bytes and audit calculations remain unchanged; a uniform clock
shift does not alter RSI, structure or gap lengths.

Settings audited: Wilder RSI 14, Close, confirmed swing bars 2 left / 2 right,
supporting-swing close break and gap >300 seconds reset all four pivots. Strict
15/85 thresholds are unchanged. These describe the earlier provisional 14-period baseline, not the corrected current RSI setup.

| Input file | First / last exported bar opens (UTC) | RSI <15 bars | RSI >85 bars | Qualifying bars |
|---|---|---:|---:|---:|
| GBPUSD_M5_history.csv | Jun 24 18:35 / Sep 30 05:10, 2026 | 2 | 23 | 0 |
| US30_M5_history.csv | Jun 18 14:50 / Sep 30 05:30, 2026 | 34 | 15 | 0 |

US30 below-15 states: 17 UNKNOWN, 16 BEARISH, 1 RANGE; above-85 states:
13 BULLISH, 2 RANGE. Therefore none meets the required countertrend entry pairing.
With current invalidation, the lowest RSI while BULLISH is about 24.824 and the
highest while BEARISH is about 76.407. Quantity changes cannot produce candidates
when those prerequisites fail.

Gap counts: GBPUSD 14, US30 80. US30 includes regular session interruptions plus
five 10-minute intervals and other longer gaps; the code resets on every interval
over five minutes. These are observed intervals, not a claim that every gap is an
export defect or a verified session schedule.

Independent JavaScript/Python implementations agreed on the primary gate/state
counts. Strict equal-pivot handling also produced zero candidates. The bundled
audit documents tie and flat-seed assumptions; it is not a native Pine runtime
or a fills/costs/P&L backtest. Read the reproducible summaries and input hashes:

- [GBPUSD summary](evidence/GBPUSD_M5_audit.json)
- [US30 summary](evidence/US30_M5_audit.json)

No performance, profitability, broker order, or original-strategy equivalence is
established by these zero-candidate checks.

## Corrected RSI 9 audit, September 30

The user's setup establishes RSI 9 Close. A new audit uses the same unchanged CSVs and structure rules; original RSI 14 reports above remain historical evidence.

| Input | RSI <15 bars | RSI >85 bars | Qualifying bars |
|---|---:|---:|---:|
| GBPUSD | 58 | 94 | 0 |
| US30 | 150 | 121 | 0 |

For US30, below-15 states are 76 UNKNOWN, 66 BEARISH and 8 RANGE; above-85 states are 37 UNKNOWN, 63 BULLISH and 21 RANGE. The lowest BULLISH RSI is 18.837 and highest BEARISH RSI is 82.587. Changing the period increases extremes but does not produce the required trend/RSI pairing in this exported sample. This supports investigating the manual structural trend interpretation; it does not establish what happened on today's photographed candle or prove Pine parity/profitability.

- [GBPUSD RSI 9 audit](evidence/GBPUSD_M5_RSI9_audit.json)
- [US30 RSI 9 audit](evidence/US30_M5_RSI9_audit.json)

## Final software handoff

The user asked to finish autonomously without more screenshots. Remaining parameters are retained as explicit engineering defaults; they are not claimed as the exact original manual swing selection. No entry is forced on the selected bearish candle. [Recorded chart observation](evidence/tradingview-selected-candle.json).

The source package now includes `COPY_STRATEGY.cmd`, `CHECK_US30_READONLY.cmd`, `windows_readonly.py` and `START_HERE.txt`. The Windows check loads the chosen existing .env explicitly before importing settings, refuses armed configurations before broker creation, and uses the reviewed MetaQuotes-Demo read-only clock preset. It uses the updated code from the extracted folder with the existing Python environment. Original settings/database remain untouched; only the generated result file is written in the new folder.

## External verification still outstanding

1. Native v1.5 display and Windows batch-launcher execution. The actual v1.4 strategy/chart and historical Data Window values have been observed. Automated checks do not stand in for Windows shell execution.
2. Native isolated US30 HTTP-to-worker run. Direct native LONG/SHORT sizing already passed, but the integrated native test still awaits an actual Windows run. The launcher automates it without asking for screenshots or enabling orders.
3. Public HTTPS endpoint and actual TradingView order-fill alert delivery.
4. Reviewed execution configuration: exact symbol mapping/allowlist, selected demo account pin, feed comparison and spread cap. Original saved gateway settings are preserved.
5. Controlled demo order/fill/protection, protection exits and interrupted/restart/recovery checks after separate order activation authorization. None has been submitted from this workspace.

The corrected 20,000-bar audits still have zero qualifying pairs under the retained structure defaults. They do not establish performance or full original-strategy equivalence. MT5 Algo Trading and broker order submission stay OFF; no live activation is authorized. The user now requested a GitHub review handoff; see [zero-trade review guide](zero-trade-review.md).


## GitHub review handoff — September 30, 2026

Repository `milad-akhtari/RSI-Trading` is accessible through the connected GitHub app, but a create-file request returned HTTP 403 (`Resource not accessible by integration`). No remote files or branches were created. The project, replay report, market-only CSV fixtures and [review guide](zero-trade-review.md) are prepared for upload. See [manual upload instructions](../GITHUB_UPLOAD.txt).
