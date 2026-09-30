# Testing and verification

## Latest checkpoint, 2026-09-30 user local date

The updated suite passes **230 tests**, 0 failures, one dependency deprecation
warning. The original 159-test application suite also passed
before the new tools were added. Broker tests use fakes; local socket support
was required for the in-process ASGI tests. No broker order was submitted.

New coverage: a read-only adapter blocks every broker mutation (including a
deliberately unsafe engine regression), armed/live settings are rejected before
connecting, LONG/SHORT sizing retains risk/margin/account/quote safeguards, and
synthetic calculations cannot change gateway settings. Candle-audit tests cover
known Wilder seed/update values, unconfirmed/future pivots, break/gap resets,
unavailable flat seeds, invalid OHLC and duplicate/out-of-order data.

User screenshots now verify Pine v1.4 compilation and historical Data Window display, native Windows MT5
read-only connection, local gateway health, and authenticated duplicate receipt.
Native US30 LONG/SHORT local read-only sizing checks passed in user screenshots;
worker receipt and the entry pause were also observed on Windows. The new isolated
HTTP-to-worker sizing check has passed locally with a fake broker and still needs
the Windows native run. No TradingView realtime alert or actual broker fill has
been verified. Reproducible candle audits found zero qualifying bars in each
uploaded 20,000-bar sample; this is not a P&L backtest or proof of native Pine
parity. See [current status](current-status.md) and [safe testing](safe-testing.md).

The isolated gateway check uses real IPv4 loopback HTTP, a private temporary
database and the production `worker.process_next` function. Its regressions cover
two-sided sizing, durable receipt/status, duplicate/conflicting payload handling,
completed-event no-retry behavior, original database/settings preservation,
armed/live refusal, stale quotes, blocked broker writes after an engine regression,
suppression of token-bearing network error text, and SQLite handle closure with commit/rollback preservation. Importing the tool does not
initialize the original gateway database. This does not test the normal daemon
worker's lease/thread lifecycle, OS-process restart or TradingView delivery.

## Recorded local verification on 2026-09-29

| Check | Actual result |
|---|---|
| `python -m pytest -o addopts='' -q` | **159 passed**, 0 failed, 1 dependency deprecation warning, 0.96 seconds |
| `python -m compileall -q automation tests` | Passed |
| `git diff --check` | Passed |
| CI YAML and local documentation links | Checked successfully |
| Prepared source and recovered Git history privacy scan | No raw account-report IDs or raw supplied media/documents found |
| Actual GitHub create-file request | HTTP 403, `Resource not accessible by integration`; repository was not initialized or changed |
| Actual Pine compilation / chart runtime | User screenshots confirm v1.1 compiled and was added to standard Binance SUIUSDT perpetual M5; diagnostic table shows M5 OK, structure and closed-bar RSI. Entry simulation remained disabled. Subsequent user screenshots confirm v1.2 is running with both readable diagnostic panels visible. Fill behavior, orders and realtime alerts remain unverified. |
| Actual realtime webhook and MT5 demo order | Not performed; selected Windows demo terminal/account and HTTPS endpoint required |
| Hosted deployment / live activation | Not performed; live remains disabled |

Environment: Linux, Python 3.12.14, pytest 9.1.1, FastAPI 0.142.0, Pydantic 2.13.5. The sole warning is the dependency's deprecation of HTTPX through Starlette TestClient; it did not fail any check. Tests ran with local socket support because the restricted sandbox stalled the in-process ASGI test client. All execution tests used a fake broker or fake MetaQuotes module; no broker connection/order was made.

## What is automated now

Run:

```bash
python -m pytest
```

The recorded local run is listed below. The suite covers:

- exact RSI threshold boundaries 14.99, 15, 15.01, 19.99, 20, 50, 80, 80.01, 84.99, 85, 85.01, 90 and 90.01;
- bullish HH/HL, bearish LH/LL, range/conflicting structure and unknown warm-up;
- pullback direction not replacing structural trend;
- 2R bracket math;
- persistent RSI extreme reset/re-entry latch;
- webhook authentication, validation, durable acceptance and deduplication;
- non-M5 webhook rejection;
- demo dry-run mode;
- demo account enforcement;
- stale-entry rejection while stale EXIT remains processable;
- broker volume-step rounding;
- symbol allowlist;
- accidental netting/reversal prevention;
- broker-side protection verification;
- emergency close on protection failure or a gap beyond the structural stop;
- EXIT no-op when the broker is already flat;
- MT5 broker-side protection remaining authoritative when a TradingView simulated EXIT arrives;
- optional close-only TradingView EXIT behavior when deliberately enabled;
- broker tick-size outward stop/target quantization;
- entry contract validation (trend + RSI + exact 2R declaration);
- hard new-entry pause and live-mode lock;
- interrupted `PROCESSING` events being quarantined for reconciliation rather than retried;
- uncertain MT5 entry outcomes: reconcile if a position exists, otherwise stop for manual reconciliation without a second order;
- account-wide total-risk cap.

These tests use a fake broker adapter. They verify application logic but **do not** prove the Pine script compiles or that an actual MT5 server accepted an order.

v1.1 regression coverage also includes direct gateway validation of all RSI boundary cases; late/other-instance exits; account/server pinning; future timestamps and stale quotes; nonfinite values; exact protective prices; partial emergency closes; FOK/IOC/unknown-result behavior in a fake MetaQuotes module; logical-trade replay conflicts; storage contention; durable entry pauses; worker leases and read-only recovery without requeuing.

## CI scope

CI is configured for Linux and Windows to run the application/static-contract suite. The earlier publication attempt was blocked; local results below are independent of GitHub CI. Check the repository Actions page for the published review revision. The fake MetaQuotes module tests request handling without a real terminal; Windows CI is still not actual broker-demo verification.

## Required TradingView checks

Screenshots reviewed on 2026-09-29 (user local date) show RSI 14 Close, swing confirmation 2/2, stop buffer 1 tick, simulated risk 1%, contract confirmation unchecked, input step/min 0.01, max 1,000,000 and point-value override 0. Properties show USD 10,000 capital, pyramiding 0, execution on bar close/order fill, default four-tick historical detail, zero commission and 1x leverage. These are observed configuration values, not proof of correct SUI contract settings. No trades were produced while the contract gate was disabled.

The diagnostic update exposes `syminfo.pointvalue`, `syminfo.mincontract`, quote currency and tick size in a separate lower-left table with readable colors. Feed minimum quantity alone does not establish exchange step, market-order maximum, fees or MT5 contract equivalence. Verify those separately before checking the contract confirmation input. Binance's public exchange-information endpoint was unavailable to the verification environment (HTTP 451), so no current SUI lot-size limits are claimed.

1. Compile `pine/rsi_trend_strategy.pine` in current Pine v6.
2. Confirm non-standard or non-M5 charts show blocked diagnostics and produce no new entries.
3. Inspect the bars where confirmed pivots become usable; ensure the entry timestamp is not back-plotted to the earlier visual pivot.
4. Verify persistent RSI extremes do not create repeated entries without reset.
5. Verify the stop and 2R target are present on the entry.
6. Recreate the alert after any script/input change.
7. Confirm the alert is **Order fills only** and webhook messages are valid JSON.
8. Test nonzero slippage: initial protection exists, the target is corrected once from simulated fill, and neither stop nor target subsequently drifts with new swings/ATR.
9. Test entry and exit on the same candle, plus a candle touching both bracket sides. Record the default emulator path and ambiguity; do not present an assumed OHLC path as a proven real sequence.
10. Check the fill-only execution guard after historical and realtime fills, and after reload. No extra entry or RSI/pivot reset may be caused by a fill execution.
11. Check confirmed structural breaks and missing M5 bars reset structure; no stale pre-break pivot restores it.

The tiny test helpers only exercise threshold/bracket/latch concepts. The new
`research.candle_audit` separately calculates reference Wilder RSI and confirmed
pivot/reset state from CSV data, with documented tie/flat-seed assumptions. It
does not simulate positions, latches, sizing, fills, costs or Pine's emulator.
Static source-contract checks cannot substitute for the platform checks above.

## Performance evaluation

No historical market backtest or performance result is claimed. The source screenshots are M1 price displays without the original RSI configuration, not a lawful complete M5 OHLC dataset. After platform compilation, record exact feed/ticker, instrument, timezone, date range, inputs, quantity metadata, commission/spread/slippage/funding assumptions and sample size for each market independently. Keep a chronological out-of-sample segment untouched while developing rules.

Report trade count, net costs/performance, win rate, average win/loss, measured realized R, profit factor, drawdown, exposure and losing streaks. If there are no trades, inspect gate counts without relaxing thresholds. Keep Bar Magnifier out of the baseline. A prop-firm target requires a separate current, account-specific rule check; these old FTMO reports do not establish compliance.

## Required MT5 demo checks

Do these on the actual selected demo broker server; record screenshots/logs without committing credentials/account identifiers:

1. Dry-run event accepted/deduplicated with no order.
2. Small demo ENTRY on the selected contract (US30 currently); test other contract families before enabling them later.
3. Verify MT5 volume obeys `volume_min`/`volume_step` and does not exceed risk cap.
4. Verify SL exists immediately on the position.
5. Verify TP is adjusted to 2R from actual fill and structural stop.
6. Trigger/close one demo position by broker-side protection; verify the corresponding TradingView EXIT cannot create an opposite trade and does not fight the broker-side exit.
7. Send a duplicate ENTRY event; no second order.
8. Pause new entries; EXIT/protection still works.
9. Simulate a malformed/stale event; no entry.
10. Restart the service with a persisted event database; no duplicate processing.
11. Force/observe an interrupted or uncertain outcome and verify it enters reconciliation status rather than blindly resubmitting.

## Acceptance status terminology

- **Implemented**: code exists.
- **Automated-tested**: local/CI unit tests passed.
- **Pine-compiled**: TradingView accepted the script.
- **TradingView-verified**: chart behavior + realtime alert observed.
- **MT5-demo-verified**: actual demo order/fill/protection/recovery observed.
- **Live-enabled**: requires later explicit user approval; currently false.


See also: [requirements-to-tests.md](requirements-to-tests.md) and [demo-checklist.md](demo-checklist.md).

## Final handoff v1.5

The displayed reason is now frozen before entry/latch mutations and retained across fill recalculations. The top table reports the last-closed RSI to two decimals and includes the confirmed decision candle's opening time in UTC, avoiding comparison with a developing RSI value. Entry, structure, sizing and protection code are unchanged from v1.4. Native v1.5 compilation/display remains pending; v1.4 native chart compilation and historical plots have now been observed.

The Windows wrapper loads an explicitly selected existing .env before settings imports, retains process-environment precedence, and refuses armed/live configurations before broker creation. The native check uses the already measured server-bound +10800-second exception, 90 synthetic index points and the existing isolated gateway tool. Ten new checks cover real loopback processing with fake native reads, original file preservation, four armed saved settings, armed process variables, missing settings, secret-safe failure reports and report-write failure. The wrapper saves a result beside the new code; it does not initialize the original database. Windows shell launchers themselves are not claimed as executed on Linux.

The observed historical screenshot at Sep 30 11:15 UTC shows RSI 9.26 / rounded strategy 9.3, state -1 BEARISH and pair 0. This verifies the selected-bar RSI agreement and explains that bar's absence of a BUY. It does not prove all-bar Pine parity or original manual trend equivalence.

## Historical diagnostics v1.4

The user confirmed trend direction wording and the bullish close-break rule. Pine v1.4 adds five read-only Data Window plots for confirmed-decision RSI, state, swing high/low and trend/RSI pairing. Snapshots precede entry/latch changes, retain their first-decision values through fill recalculations and are unavailable on bars without a matching confirmed decision. Removing the new diagnostic block and reverting version labels reproduces v1.3 byte-for-byte; execution logic is unchanged. Existing 220 tests pass. These checks do not substitute for actual TradingView compilation/display or fill-recalculation runtime verification, which remain pending.

The latest user screenshot confirms existing v1.2 now uses RSI 9 Close on CAPITALCOM:US30 M5. The strategy table reports a closed decision while the separate RSI can show the developing bar, so compare the same historical candle in the Data Window rather than treating simultaneous last-value labels as parity evidence.

## User-confirmed RSI correction v1.3

The setup screenshot supplied September 30 shows RSI length 9, Close, separate SMA 14, chart timeframe, divergence off and wait for timeframe closes enabled. Pine v1.3 changes only the RSI default and version labels/comments. Thresholds, structure, confirmed-close decisions, quantities and execution safeguards remain unchanged. Existing chart inputs must explicitly be changed to 9. Native v1.3 compilation/runtime is pending.

The corrected audits retain the same source hashes and structure counts. US30 extremes increase from 34/15 to 150/121 (below 15 / above 85); GBPUSD from 2/23 to 58/94. Qualifying bars remain zero in both samples. Separate RSI 9 summaries are recorded alongside the original 14-period baseline; no fills or profitability are inferred.

## Display troubleshooting revision v1.2

The user reported that both tables remained absent after re-pasting the metadata update. The exact chart-side cause has not been established; the report is not evidence of a compiler error. The v1.2 display revision populates both tables on every script calculation rather than conditioning writes on last-bar flags and uses a distinct strategy title for version identification. Signal/order calculation settings and entry guards remain intact. Remove the previous chart instance before adding v1.2 with Show diagnostics enabled. Actual display recovery must be confirmed by a screenshot of the v1.2 chart title and feed table.

## Observed v1.2 chart result

User screenshots on 2026-09-29 (Los Angeles date) confirm v1.2 loaded successfully on standard `BINANCE:SUIUSDT.P` M5 and both diagnostic panels appeared. The feed reports point value 1, minimum quantity 0.001, quote currency USDT and tick size 0.0001. Configured quantity step/min/max remain 0.01 / 0.01 / 1,000,000; contract confirmation remains unchecked. These chart-reported values do not establish current Binance market-order limits or an equivalent MT5 contract.

The displayed state was UNKNOWN with insufficient/broken structure, RSI approximately 72.86, no active bracket and zero entry orders. Gate counts were unknown 2,587, range 1,668 and RSI 2,386, with position/reset and stop/size counts all zero. Inference: every evaluated bar in this loaded sample failed at the structural or RSI stage before contract/size eligibility. Enabling contract confirmation alone would not create trades for the same loaded sample. This is a diagnostic finding, not a strategy performance result.

Later screenshots verified a non-M5 chart displays BLOCKED and M5 returns OK.
Current checks focus on original RSI/trend equivalence, native read-only sizing,
simulation costs/margin and qualifying entries/fills. Local webhook receipt and
deduplication are verified; TradingView realtime webhook delivery, actual MT5
demo orders and live trading remain unverified.
