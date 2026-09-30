# Changelog

## Unreleased

- Finished v1.5 software handoff: frozen pre-order diagnostic reason, closed RSI/time display, clipboard strategy launcher and isolated Windows read-only gateway launcher using the existing environment/settings. Recorded observed selected-bar RSI agreement and bearish-state rejection. Added ten desktop-wrapper checks (230 total); native launcher/order/delivery verification remains external.

- Recorded user confirmation of bullish HH+HL, bearish LL+LH and skip BUY after an M5 close below the latest higher low. Pine v1.4 adds read-only historical decision snapshots in the Data Window; execution logic unchanged. Native compilation/display pending.

- Pine v1.3 corrects the RSI default from provisional 14 to user-confirmed 9 Close. Separate SMA 14 remains display smoothing. Recorded corrected audits: US30 150/121 and GBPUSD 58/94 RSI extremes, zero qualifying bars under unchanged trend rules. Existing chart inputs need explicit update; native v1.3 compilation remains pending.

- Added an isolated read-only US30 check through real loopback HTTP, temporary SQLite, production worker processing and native sizing. Separate temporary token/port/map preserve normal gateway data and settings; all broker writes blocked. Extracted the HTTP app factory to avoid database initialization when importing this tool. SQLite transaction contexts now explicitly close handles while preserving commit/rollback, allowing Windows cleanup. Added 12 checks (220 total); native Windows tool result pending.
- Recorded the separate RSI indicator's current inputs (14 Close, additional SMA 14, chart timeframe, divergence off); historical entry line/settings remain unconfirmed. Pine rules unchanged.

- Recorded user screenshots confirming native US30 LONG/SHORT read-only sizing (0.1 lot, USD 10 risk, USD 25.78 margin), Windows gateway worker processing, entry pause rejection, and saved event status re-read. Strategy signals, webhook-to-US30 sizing and native order/fill checks remain pending.

- Diagnosed an observed +3h US30 quote timestamp on MetaQuotes-Demo. Added an explicit, server-bound quote clock correction with temporary read-only CLI flags; default UTC behavior and original freshness limits are preserved. Added 18 regression checks (208 total). Corrected historical timestamp confidence in the status report; native corrected sizing remains pending.

- Added a native synthetic MT5 sizing/margin check that refuses armed configurations and blocks all broker mutations independently; gateway settings are unchanged.
- Added an explicit-settings CSV candle audit with source hashes, confirmed pivots, structural resets and invalid-data rejection. Recorded zero qualifying bars in uploaded GBPUSD/US30 20,000-bar samples; native Pine parity and profitability are not claimed.
- Added 31 regression tests; full local suite now 190 passing. Updated actual Windows, TradingView, gateway and US30 contract evidence with remaining native acceptance checks.

- User screenshots confirm v1.2 chart loading and both diagnostic panels on SUI perpetual M5. Recorded feed metadata and the absence of eligible entries in the loaded sample; order/fill and broker checks remain pending.

- Labeled the display revision v1.2 and populated both tables on every script calculation, including initial historical loading, to remove display dependence on last-bar flags. Platform verification is still pending.

- Recorded screenshot evidence that Pine v1.1 compiled and was added to a standard Binance SUI perpetual M5 chart; actual simulated fills and broker demo verification remain pending.
- Improved diagnostic contrast and added a separate feed metadata panel for point value, minimum quantity, quote currency, tick size and contract-confirmation status. This display-only update requires a fresh TradingView compile; entry rules, sizing and execution behavior are unchanged.

## 0.1.1 - 2026-09-29

- Recovered the original implementation and local commit history.
- Added fill-only Pine recalculation for targets based on simulated fills, with guards preventing entry decisions during fill recalculations.
- Added structural invalidation/gap resets, chart-local RSI source choices, account-currency sizing, contract confirmation and stable chart-instance event identity.
- Added schema 1.1 with explicit chart tick precision, finite-value validation and outward 2R rounding checks.
- Pinned the MT5 account/server and rejected stale quotes/future entry timestamps.
- Restricted market submissions to FOK/IOC, verified exact protective prices and confirmed complete emergency closes.
- Matched optional EXIT closes to the exact trade so delayed/other-instance exits cannot close newer positions.
- Added durable reconciliation entry pauses, one-worker leases, read-only operator recovery and access-log token protection.
- Added regression tests, schema/example fixtures and Linux/Windows CI configuration. Actual CI, Pine compile, realtime alerts and broker demo verification remain separate pending checks.
- GitHub publication was attempted but the connected app lacked access to write this repository (HTTP 403); no remote success is claimed.
- Live trading remains disabled.

## 0.1.0 - 2026-09-29

- Added Pine v6 RSI Trend Strategy implementation.
- Added confirmed M5 structural trend/range state and strict RSI boundaries.
- Added structural stop, fixed 2R target, repeat-extreme lockout, diagnostics and JSON order-fill payloads.
- Added durable FastAPI/SQLite webhook gateway.
- Added MetaTrader 5 adapter with demo-account enforcement, broker-aware risk sizing, broker tick-size normalization, protection verification, idempotency, reconciliation safeguards and emergency close behavior.
- Added uncertain-order and interrupted-worker quarantine logic to prevent blind duplicate retries.
- Made broker-side MT5 SL/TP authoritative for v1 protective exits; TradingView simulated EXIT events are informational by default.
- Added source audit, setup docs, test plan and example configuration.
- Live trading remains disabled.
