# Safe local test commands

For the finished package, double-click `CHECK_US30_READONLY.cmd`. It chooses the Python environment beside the launcher or the user's existing Downloads/RSI-Trading installation, explicitly loads that installation's .env and runs the updated isolated tool. It writes `US30_READONLY_RESULT.json` in the extracted release folder. The embedded clock preset is the previously measured MetaQuotes-Demo +10800s exception; different servers or stale clocks are refused. It never edits or arms saved settings. Windows batch execution remains a native external check.

These tools support the current demo-only verification stage. They do not change
Pine entry thresholds or persist any change to `.env`. Keep MT5 Algo Trading OFF.

## Install the updated project

Stop the gateway terminal with Ctrl+C. Open the updated ZIP and copy its inner
`RSI-Trading` folder into your existing Downloads folder. Replace the matching
project files when Windows asks. Do not delete your existing project folder;
the archive excludes your `.env`, virtual environment and event database.

Open a terminal in `C:\Users\milad\Downloads\RSI-Trading`. No extra packages are
required beyond the already installed project requirements.

## Native MT5 synthetic sizing check — no orders

Keep these switches unchanged:

```text
EXECUTION_MODE=demo
DEMO_ORDER_SUBMISSION_ENABLED=false
LIVE_TRADING_ENABLED=false
NEW_ENTRIES_ENABLED=false
EXECUTE_TRADINGVIEW_EXIT_ALERTS=false
```

Run the US30 LONG check:

```bat
.\.venv\Scripts\python.exe -m automation.dry_run_mt5 --symbol US30 --side LONG --stop-distance 100
```

Then the SHORT check:

```bat
.\.venv\Scripts\python.exe -m automation.dry_run_mt5 --symbol US30 --side SHORT --stop-distance 100
```

`100` means 100 **index price points**, not 100 broker increments of 0.01. This is
a synthetic stop for exercising sizing and margin; it is not a strategy entry or
a proposed trade. Risk defaults to 1%, cannot exceed the configured per-entry cap,
and is calculated with the broker's native `order_calc_profit()`/margin functions.

Expected success includes `synthetic_test_only: true`, `broker_writes_blocked:
true` and `result.status: DRY_RUN_DEMO`, plus volume, SL, TP, risk and margin.
The tool enables calculation eligibility only in an in-memory settings copy;
gateway settings and .env remain unchanged. A read-only adapter independently
rejects opening orders, modifying protection and closing positions, even if an
execution-engine regression tries to do so. No event is queued in SQLite.

Rejection is useful evidence. Stale/future quotes, live/wrong accounts, existing
positions, minimum lot or margin problems are not bypassed. Record the output
and diagnose the exact cause. Do not loosen freshness/risk gates to make it pass.
The tool refuses a live or already armed configuration before connecting.

### Verified quote clock exception

The user's 2026-09-29 screenshot shows computer UTC `2026-09-30T03:57:37.433437`
and raw US30 tick time interpreted as UTC `2026-09-30T06:57:35.170`, with age
`-10797.74` seconds. This is consistent with a +10,800-second feed clock offset;
it does not establish that all MT5 servers or all historical bars use this clock.
MetaQuotes documents UTC tick/bar times, so the default correction remains zero.

For a read-only test on the observed `MetaQuotes-Demo` server only:

```bat
.\.venv\Scripts\python.exe -m automation.dry_run_mt5 --symbol US30 --side LONG --stop-distance 100 --quote-time-offset-seconds 10800 --quote-time-offset-server MetaQuotes-Demo
```

Repeat with `--side SHORT` after LONG succeeds. These flags only change this
process's settings; `.env` stays unchanged. The adapter subtracts the explicitly
provided offset from positive tick timestamps and requires an exact match to the
connected server on every symbol read. The original 30-second freshness and
10-second future-skew limits still apply. No age-based automatic correction or
replacement with the computer's current time is performed. Recheck the measured
clock after a server switch or seasonal clock change; do not reuse this exception
on another server. Successful output includes the normalized time and offset.

For a later gateway setup, the corresponding settings are
`MT5_QUOTE_TIME_OFFSET_SECONDS` and `MT5_QUOTE_TIME_OFFSET_SERVER`; defaults are
zero/blank. Do not persist or arm gateway settings during this read-only stage.

References: [native tick fields](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfotick_py)
and [documented UTC time convention](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksfrom_py).

This does **not** verify native order acceptance, fills, broker-side protection,
TradingView transport or the strategy's profitability. Order activation remains
a later stage in [the demo checklist](demo-checklist.md).

## Isolated US30 webhook-to-worker check — no orders

This exercises actual local HTTP receipt, duplicate detection, conflicting-payload
rejection, durable SQLite queuing, production `worker.process_next`, native sizing
and status retrieval for LONG and SHORT. It binds only `127.0.0.1` on an available
temporary port, uses a fresh private token and temporary database, then shuts down.
It can run while the normal port-8000 gateway remains open. No new packages needed.

```bat
.\.venv\Scripts\python.exe -m automation.check_us30_gateway --stop-distance 90 --quote-time-offset-seconds 10800 --quote-time-offset-server MetaQuotes-Demo
```

The 90-point synthetic stop is only a test input. It leaves some sizing room below
the 1% risk cap for this USD 1,000 / minimum 0.1-lot contract if the quote moves
between receipt and processing. It does not change the Pine structural stop or
any risk gate. The temporary `CAPITALCOM:US30` -> `US30` mapping and calculation
eligibility are internal to this test. All broker mutations remain independently
blocked, and armed/live configurations are refused before startup. It neither
edits `.env` nor opens the regular event database. Failed safety gates are reported
without bypassing them; no event is placed in the normal gateway queue.

Expected success: `status: GATEWAY_CHECK_PASSED`; two `checks` for LONG/SHORT,
each `durable_status: DONE`, `attempts: 1`, and `result.status: DRY_RUN_DEMO`.
Output includes computed risk/volume and native margin. Broker writes are blocked,
settings/database unchanged, duplicates detected and completed events not retried.

This is synthetic loopback transport and worker processing. It does not verify
actual TradingView order-fill alerts, a public HTTPS endpoint, original strategy
signals, normal worker daemon/lease startup, OS-process restart, broker orders,
fills/protection or profitability. The saved-result check re-opens the temporary
SQLite store; it is not presented as an OS-process restart test.

## Reproduce the candle eligibility audit

Explicit parameters are required so historical RSI settings are not guessed:

```bat
.\.venv\Scripts\python.exe -m research.candle_audit US30_M5_history.csv --rsi-length 9 --source close --swing-bars 2
```

The source can be close/open/high/low/hl2/hlc3/ohlc4. Use only settings actually
confirmed for the strategy. The current input set is a provisional implementation
baseline, not a search for settings that produce trades. No parameter optimization
or P&L simulation is performed. A `--ties strict` run checks equal-pivot sensitivity.

Invalid OHLC, nonfinite values, malformed/off-grid timestamps, duplicate or
unordered rows and empty input cause a failed audit, rather than a healthy zero.
Valid gaps over five minutes retain their exported timing and reset structure.
Pivot origins predating a reset cannot restore an old trend; future bars cannot
backdate a candidate. Output includes the source SHA-256, date range, explicit
settings, state/gate counts and any qualifying decision timestamps.

The audit is a reference calculation. Native Pine tie/flat-seed behavior, position
latches, quantity/margin, fills, costs and performance are outside its scope.
