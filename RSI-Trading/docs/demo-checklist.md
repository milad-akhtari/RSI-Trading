# End-to-end demo verification checklist

Do not change `LIVE_TRADING_ENABLED=false` during this checklist.

## Phase A — read-only MT5 connection

- [ ] MT5 desktop terminal is open on Windows.
- [ ] Logged into the intended **demo** account.
- [ ] Keep Algo Trading OFF during read-only connection and calculation checks. Confirm required permissions before Phase D.
- [ ] `.env` contains the correct demo terminal/server details and a unique webhook token.
- [ ] Run `python -m automation.diagnose_mt5`.
- [ ] Output says `is_demo: true`.
- [ ] Confirm the exact broker symbols for forex, Gold, US30 and BTC that will be enabled.
- [ ] Pin the expected `MT5_LOGIN` and exact `MT5_SERVER`; verify a different account/server is rejected.
- [ ] Confirm symbol/feed mappings are approved for the actual contract; the example map is not evidence of equivalence.

## Phase B — gateway dry run, zero orders

Before changing gateway eligibility, run `python -m automation.dry_run_mt5
--symbol US30 --stop-distance 100` and the SHORT variant. This independent
read-only check requires submission disabled and does not edit .env. See
[safe testing](safe-testing.md). Native calculation success and local gateway
receipt are separate checks; neither establishes realtime TradingView delivery.

Keep:

```text
EXECUTION_MODE=demo
DEMO_ORDER_SUBMISSION_ENABLED=false
NEW_ENTRIES_ENABLED=true
LIVE_TRADING_ENABLED=false
```

- [ ] Start `python -m automation --host 127.0.0.1 --port 8000`.
- [ ] Expose it through HTTPS/443 reverse proxy or tunnel.
- [ ] `/health` shows demo mode, live false.
- [ ] TradingView webhook is accepted.
- [ ] `/status/<token>/<event_id>` ends `DONE` with `DRY_RUN_DEMO`.
- [ ] No MT5 order exists.
- [ ] Repeat the same event ID; it is marked duplicate and creates no second event/order.

## Phase C — TradingView strategy verification

- [ ] Paste `pine/rsi_trend_strategy.pine` into Pine Editor.
- [ ] It compiles as Pine v6 with no errors/warnings that change behavior.
- [ ] Use standard M5 chart only.
- [ ] Verify diagnostics state and RSI.
- [ ] Verify the linear contract, quantity units/min/max/step, point value and costs; enable the contract confirmation input.
- [ ] Verify wrong timeframe/non-standard chart blocks new entries.
- [ ] Verify entry marker is not backdated to an unconfirmed pivot.
- [ ] Verify active structural stop and 2R target are visible.
- [ ] Add nonzero simulated slippage; confirm target is 2R from the simulated fill and the stop stays frozen.
- [ ] Confirm fill recalculations never create intrabar/repeated entries or retrospectively update structure.
- [ ] Confirm structure is invalidated by a supporting-swing close break, and M5 gaps require fresh swings.
- [ ] Create alert: strategy → **Order fills only** → message `{{strategy.order.alert_message}}`.

## Phase D — arm small demo orders

Only after A–C pass:

```text
EXECUTION_MODE=demo
DEMO_ORDER_SUBMISSION_ENABLED=true
NEW_ENTRIES_ENABLED=true
LIVE_TRADING_ENABLED=false
EXECUTE_TRADINGVIEW_EXIT_ALERTS=false
```

- [ ] Use demo-only symbols and conservative risk settings.
- [ ] First ENTRY reaches MT5 once.
- [ ] MT5 volume respects broker min/max/step.
- [ ] Position has broker-side SL immediately.
- [ ] Position has broker-side target based on actual fill and structural stop.
- [ ] Stored event status is `DONE` / `DEMO_ORDER_OPENED`.
- [ ] Duplicate event cannot add a second position.
- [ ] Existing/manual same-symbol position blocks a new bot entry.
- [ ] Broker-side TP or SL can close position without needing the webhook service to stay alive.
- [ ] Later TradingView EXIT does not open a reverse position or fight the broker-side exit.

## Phase E — failure/recovery demo checks

- [ ] Stop new entries and confirm existing broker protection remains.
- [ ] Restart gateway; SQLite history persists.
- [ ] An event left in `PROCESSING` is quarantined as `RECONCILIATION_REQUIRED`, not resent.
- [ ] Disconnect scenario does not cause blind duplicate entry retry.
- [ ] Reconnect and compare broker positions to event database before any manual retry.
- [ ] The unresolved outcome persists an entry pause across all chart instances and restarts.
- [ ] A second worker for this database is refused.
- [ ] A late/other-instance optional EXIT cannot close a newer position.
- [ ] Recovery resumes entries only after operator review and never requeues an old event.

## Acceptance

End-to-end demo is accepted only when screenshots/logs show:

1. Pine compiles and behaves on M5.
2. TradingView realtime webhook reaches gateway.
3. Exactly one MT5 demo entry is created from one entry event.
4. Broker-side SL/TP is present and valid.
5. Duplicate/restart/failure safeguards behave as documented.

Even after all boxes pass, **live remains disabled until a separate explicit activation approval.**
