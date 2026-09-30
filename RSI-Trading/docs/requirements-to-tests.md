# Requirements-to-tests map

This map separates **logic tests**, **Pine compilation/TradingView checks**, and **real MT5 demo evidence**. Passing Python tests is not represented as Pine compilation or broker verification.

| Requirement | Automated evidence | TradingView / MT5 acceptance evidence |
|---|---|---|
| M5 standard chart only | `tests/test_pine_contract.py`, webhook schema rejects non-M5 | Pine compile; 1m/non-standard chart produces no entries |
| Bullish + RSI < 15 BUY | `test_strategy_logic.py`, `test_thresholds.py` | Observe qualifying M5 signal |
| Bearish + RSI > 85 SELL | `test_strategy_logic.py`, `test_thresholds.py` | Observe qualifying M5 signal |
| Strict 15 / 85 / 90 boundaries | parameterized threshold tests | Strategy Tester spot-check on boundary fixture/known bars |
| Range/unknown = no entry | `test_strategy_logic.py` | Diagnostics show block on ambiguous structure |
| Trend survives opposite pullback until structure changes | `test_strategy_logic.py` | Inspect confirmed swings on chart |
| No future pivot leakage | source-contract guard inspection; Python has no Pine pivot runtime | Verify signal occurs only after right-side pivot confirmation |
| One entry per continuous RSI extreme | `ExtremeLatch` test | Realtime/strategy replay check |
| Structural stop + 2R target | `test_strategy_logic.py`, execution-engine tests | Plot bracket; verify MT5 SL/TP |
| Tick/lot rounding | execution-engine tick + volume tests | Confirm actual demo contract metadata and resulting order |
| Risk caps / single-position protection | execution-engine tests | Demo account check across configured charts |
| Wrong symbol / mapping rejected | execution-engine tests | Send test alert for unmapped ticker |
| Duplicate webhook cannot duplicate order | webhook SQLite dedupe test | Replay same event ID and inspect MT5 |
| Stale ENTRY rejected | execution-engine test | Delayed test event produces no order |
| Protective exits remain active when entries paused | execution design + tests | Pause new entries with open demo position; SL/TP remains |
| Broker protection authoritative | execution-engine EXIT tests | Let broker SL/TP close demo trade; later TV EXIT is no-op/informational |
| Unknown send outcome is not blindly retried | uncertain-outcome tests | Induce/observe disconnect only in controlled demo verification |
| Restart during processing does not auto-resubmit | SQLite reconciliation test | Restart with PROCESSING fixture and inspect status |
| Live account blocked in demo mode | execution-engine test | Connect demo only for acceptance |
| Live trading disabled | settings + execution-engine live-lock test | `LIVE_TRADING_ENABLED=false` in handoff config |
| Webhook response is durable and quick | SQLite accept-before-202 test | TradingView webhook log shows delivery; worker processes asynchronously |
| Alert stream is strategy order fills, not duplicate setup alerts | Pine contract test / source review | Alert configured as “Order fills only” |
| Broker-aware sizing | fake-broker unit tests | Real demo uses `order_calc_profit` + `volume_step` and records resulting volume |
| Immediate broker-side SL/TP | engine/protection tests | Actual MT5 position shows SL and TP immediately after demo entry |
| Failed protection triggers fail-safe | protection-failure unit test | Controlled demo failure only if safely reproducible |
| Fill recalculation cannot create/re-arm entries | Pine source-contract guard checks only | Replay actual fills including same-bar exits; no intrabar/duplicate entry |
| Structural break and missing bars reset swings | Pine source-contract inspection only | Confirm fresh swings after supporting-swing break or M5 gap |
| Actual-fill target and precise protection | `test_execution_regressions.py` | Nonzero-slippage Pine check and MT5 actual-fill 2R check |
| Late EXIT cannot close newer/other-instance trade | `test_execution_regressions.py` | Old demo EXIT with newer position remains a no-op |
| Uncertain outcomes pause other chart entries | `test_recovery.py` | Persisted pause survives restart; broker protection stays active |
| One worker and recovery without requeue | `test_recovery.py` | Start second Windows worker; local recovery never resends old event |
| Partial/unknown order adapter outcomes | `test_mt5_adapter.py`, fake MetaQuotes module | Selected demo server accepts FOK/IOC and reconciles actual fills |
| Read-only calculation cannot send/modify/close orders | `test_readonly_dry_run.py`, including engine regression and armed-config rejection | Run native LONG/SHORT check; .env and account positions remain unchanged |
| Isolated HTTP-to-worker read-only check preserves original data/settings | `test_gateway_readonly.py`: real loopback HTTP, duplicate/conflict, SQLite reopen/no-retry, stale/live/refused writes, import isolation | Run `automation.check_us30_gateway` on native Windows MT5; not a TradingView signal or normal daemon/process restart test |
| CSV audit uses confirmed pivots and rejects invalid data | `test_candle_audit.py`: future-prefix invariance, breaks, gaps and malformed/duplicate data | Compare original RSI/trend settings and native Pine chart bars |

## Current evidence state

- Python/application automated tests: passing locally.
- Python syntax/bytecode compilation: passing locally.
- Pine source contract/static checks: passing locally.
- **Actual Pine compilation/diagnostic display: observed in user screenshots.**
- **Native MT5 read-only connection and local gateway receipt/deduplication: observed.**
- **Native US30 LONG/SHORT local sizing, worker entry pause and saved status: observed.**
- **Isolated US30 HTTP-to-worker native sizing: Windows run pending.**
- **Realtime TradingView webhook verification: not yet performed.**
- **Actual MT5 demo order/fill/protection verification: not yet performed.**
- **Live activation: disabled and not approved.**

See [current evidence](current-status.md) for the exact limits of those checks.

## Desktop handoff

| Requirement | Automated evidence | Native acceptance evidence |
|---|---|---|
| One-click read-only Windows handoff | `test_windows_readonly.py`: explicit existing settings, armed refusal before broker creation, report redaction/write failure, original file preservation | Batch launch/native SDK run pending; no broker writes allowed |
