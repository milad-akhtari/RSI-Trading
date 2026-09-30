# RSI Trend Strategy — TradingView + MetaTrader 5

This project contains the **RSI Trend Strategy** as a TradingView Pine v6 strategy plus a separate MetaTrader 5 execution gateway. Pine compilation, native read-only MT5 connectivity and local webhook receipt/deduplication have been observed. Actual strategy fills, realtime TradingView alerts and MT5 demo orders remain unverified. The intended path is:

**TradingView M5 strategy -> order-fill webhook -> execution gateway -> MT5 demo account -> broker-side SL/TP**

## Reviewing the zero-trade result

Start with [docs/zero-trade-review.md](docs/zero-trade-review.md). It distinguishes confirmed rules from engineering assumptions and includes commands to reproduce the historical entry audit without MT5.

## Finished software package

Start with [START_HERE.txt](START_HERE.txt). `COPY_STRATEGY.cmd` copies the complete Pine source. `CHECK_US30_READONLY.cmd` reuses your existing Windows environment/settings and runs both isolated US30 checks without modifying the installation or submitting orders. The saved result is `US30_READONLY_RESULT.json`. Native order/fill verification and public TradingView delivery remain external checks, not completed claims.

## Current safety state

| Component | Status |
|---|---|
| Pine strategy source | v1.5 clarifies last-closed decision/time; v1.4 compiled and historical diagnostics observed on US30 M5 |
| Python execution gateway | Implemented; fake-broker regression tests |
| Automated application tests | **230 passing**, see [recorded checks](docs/testing.md) |
| GitHub review handoff | Prepared; connected-app write returned HTTP 403. See [upload steps](GITHUB_UPLOAD.txt) and [review guide](docs/zero-trade-review.md) |
| Native MT5 connection | Read-only connection to USD demo account verified |
| Local gateway | Health, duplicate receipt and entry-pause worker processing verified; isolated US30 HTTP-to-sizing check pending on Windows |
| Native US30 sizing | LONG and SHORT local read-only commands passed; no broker orders |
| MT5 demo execution | Order/fill/protection checks pending; orders disabled |
| Live trading | **DISABLED** |

The execution configuration defaults to **no order submission** and **new entries paused**. A real MT5 account is rejected in demo mode.

Read [current evidence and remaining work](docs/current-status.md) and
[safe one-command testing](docs/safe-testing.md). The uploaded 20,000-bar GBPUSD
and US30 samples produced zero qualifying bars under both the earlier RSI 14 baseline and confirmed RSI 9 Close with
2/2 swing settings. This is an entry-condition audit, not a profitability result;
the user's manual trend interpretation still needs confirmation.

## Strategy baseline

- Standard **5-minute** chart only.
- Bullish structural trend + **RSI < 15** -> BUY candidate.
- Bearish structural trend + **RSI > 85** -> SELL candidate.
- Range/unknown -> no new entry.
- RSI exactly 15 / 85 do not qualify.
- RSI > 90 is only a stronger SELL label.
- Planned target = **2R** from a structural stop.
- No higher/lower timeframe confirmation.
- No divergence, order blocks, trailing, breakeven, martingale, grid or averaging logic has been silently added.

See [docs/strategy-spec.md](docs/strategy-spec.md) for the exact deterministic translation.

## Repository layout

```text
pine/rsi_trend_strategy.pine    TradingView Pine v6 strategy
automation/                     HTTPS gateway + MT5 execution worker
config/                         example symbol map
docs/strategy-spec.md           executable rules / assumptions
docs/source-review.md           evidence and conflicts
docs/tradingview-setup.md       TradingView setup
docs/mt5-setup.md               MT5 demo setup
docs/testing.md                 tests + acceptance procedure
docs/requirements-to-tests.md   traceability map
docs/demo-checklist.md           end-to-end demo runbook
tests/                          automated logic and execution tests
research/candle_audit.py         explicit-settings CSV entry-condition audit
automation/dry_run_mt5.py        native sizing check with broker writes blocked
automation/check_us30_gateway.py isolated HTTP/SQLite/worker native read-only check
.env.example                    safe configuration template
```

## Quick local test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Beginner TradingView setup

1. Open the target symbol on a **standard 5-minute chart**.
2. Paste `pine/rsi_trend_strategy.pine` into Pine Editor.
3. Compile/add it to the chart.
4. Review the diagnostics table before trusting any backtest.
5. Verify the exact linear contract/quantity inputs and enable the contract confirmation input for simulation orders.
6. Create an alert for **Order fills only**.
7. Alert Message: `{{strategy.order.alert_message}}`.
8. Webhook URL: `https://YOUR_HOST/tradingview/YOUR_WEBHOOK_TOKEN`.

Full steps: [docs/tradingview-setup.md](docs/tradingview-setup.md).

## Beginner MT5 demo setup

The official MetaTrader5 Python package talks to the desktop MT5 terminal, so use Windows for the execution host.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m automation --host 127.0.0.1 --port 8000
```

First run the read-only MT5 diagnostic:

Replace the example webhook token with a generated private token first. Set the expected MT5 demo login/server before arming any submission; no credentials belong in chat or Git.

```powershell
python -m automation.diagnose_mt5
```

Then start with:

```text
EXECUTION_MODE=demo
DEMO_ORDER_SUBMISSION_ENABLED=false
LIVE_TRADING_ENABLED=false
NEW_ENTRIES_ENABLED=false
EXECUTE_TRADINGVIEW_EXIT_ALERTS=false
```

Use an HTTPS tunnel/reverse proxy for TradingView. After dry-run verification, demo orders can be armed while live remains false. MT5 broker-side SL/TP remains authoritative for protective exits; TradingView simulated EXIT fills are reconciliation events by default. See [docs/mt5-setup.md](docs/mt5-setup.md).

All charts for one account must share one service/database/worker. Unknown order outcomes pause later entries durably; `python -m automation.recovery` shows the pause. Recovery never resubmits an order. Keep existing broker protection when pausing entries or stopping the service.

## Important implementation notes

The user's setup screenshot supplied September 30 confirms RSI length 9, Close, a separate SMA 14 plot, chart timeframe, divergence off and wait for timeframe closes enabled. Pine v1.3 now defaults to RSI(9, close). SMA 14 does not replace the RSI period or act as an entry gate. Existing chart instances may retain the old input: explicitly set strategy RSI length to 9. The user confirmed HH+HL bullish, LL+LH bearish, and skip BUY after a confirmed M5 close below the latest higher low. Exact pivot selection and reset/re-establishment remain unresolved.

The supplied historical FTMO chart screenshots visibly use **1-minute** display intervals. They are useful historical examples but do not override the user's explicit M5 strategy requirement.

## Live activation

No real-money activation is part of this handoff. `LIVE_TRADING_ENABLED=false` must remain in place until the user explicitly approves live activation **after** successful end-to-end demo verification.
