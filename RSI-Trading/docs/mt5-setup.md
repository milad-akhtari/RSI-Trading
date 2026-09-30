# MetaTrader 5 demo execution setup

## Architecture

`TradingView strategy order-fill alert -> HTTPS webhook -> durable SQLite event -> worker -> local MT5 terminal -> demo trade server`

MetaTrader 5 is authoritative for broker account state, symbol specifications, positions, fills and protective orders.

## Why the execution service runs on Windows

MetaQuotes' official `MetaTrader5` Python package connects to a locally installed MetaTrader 5 desktop terminal through `initialize()`. The demo execution host therefore needs Windows, the MT5 terminal, Python, and the logged-in demo account.

## 1. Create/connect a demo account

Use a MetaTrader 5 **demo** account. The service deliberately rejects a non-demo account while `EXECUTION_MODE=demo`.

Do not paste account passwords into GitHub or Pine. Store them only in the local `.env` if the terminal cannot reuse its saved login.

## 2. Install the runtime

From PowerShell in the repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` locally. The runtime loads this file automatically through `python-dotenv`; environment variables still override it.

Set a generated `WEBHOOK_TOKEN` before running even the read-only diagnostic. The example token is deliberately rejected. You can generate a token locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep the value private.

Start safe first:

```text
EXECUTION_MODE=demo
DEMO_ORDER_SUBMISSION_ENABLED=false
LIVE_TRADING_ENABLED=false
NEW_ENTRIES_ENABLED=false
```

## 3. Verify the connection without placing an order

Before starting the webhook service, run the read-only diagnostic:

```powershell
python -m automation.diagnose_mt5
```

It prints demo/live status, equity/margin state and the configured symbols' broker tick/volume metadata. It never calls `order_send()`.

## 4. Verify MT5 symbols

Broker symbol names vary. The historical FTMO reports include examples such as `US30.cash`, `BTCUSD`, and `GBPUSD`; Gold is commonly broker-specific as well. Inspect **Market Watch** in the actual demo terminal and edit:

- `ALLOWED_MT5_SYMBOLS`
- `SYMBOL_MAP_JSON`

Mappings in the example are placeholders, not verification that a Bitcoin spot feed, a CFD or a forex feed is equivalent. Select the exact TradingView ticker/feed and corresponding broker contract. Confirm contract family, quote currency, tick value, volume limits and spread policy. Supply `MT5_LOGIN` and the exact `MT5_SERVER` to pin the demo account before enabling submission. A terminal account/server change is then rejected.

The gateway refuses an unmapped symbol.

## 5. Start the service

Generate a long random webhook token and set `WEBHOOK_TOKEN`.

Run:

```powershell
python -m automation --host 127.0.0.1 --port 8000
```

The local HTTP port is not sent directly to TradingView. Put an HTTPS reverse proxy/tunnel in front of it so TradingView receives a public HTTPS URL on port 443. No hosted service or infrastructure purchase is included in the source package. Keep webhook URL tokens out of proxy/access logs as well as application logs. The launcher disables Uvicorn access logs by default.

## 6. Dry-run webhook test

Keep order submission disabled. Send a valid TradingView alert. Check that:

For the worker to calculate a dry run, set `NEW_ENTRIES_ENABLED=true` while leaving `DEMO_ORDER_SUBMISSION_ENABLED=false` and `LIVE_TRADING_ENABLED=false`. With new entries false, the expected result is a rejection, not a dry run.

- `/health` reports demo mode and live disabled;
- the event appears in `data/events.sqlite3`;
- the worker records a `DRY_RUN_DEMO` result;
- no MT5 order appears.

## 7. Arm demo orders

Only after the dry run is correct:

```text
DEMO_ORDER_SUBMISSION_ENABLED=true
NEW_ENTRIES_ENABLED=true
LIVE_TRADING_ENABLED=false
```

Restart the service. It will still reject a real account.

## 8. What happens on ENTRY

The worker:

1. rejects stale or duplicate entries;
2. confirms the connected account is demo and expert/API trading is allowed;
3. maps/allowlists the symbol;
4. refuses a symbol with an existing position to avoid accidental netting/reversal;
5. gets the current broker bid/ask;
6. validates the TradingView structural stop against the actual quote;
7. uses MT5 `order_calc_profit()` to calculate one-lot stop loss in account currency;
8. sizes volume from account equity and rounds down to the broker `volume_step`;
9. checks total bot risk, position count, spread and estimated margin;
10. sends a market order with SL/TP attached;
11. reconciles the exact position using symbol, side, magic and trade-identity comment;
12. keeps the structural stop normalized to the broker's executable tick size before sizing/submission;
13. recalculates the final target to at least the intended 2R after tick quantization, using the actual broker fill;
14. updates/validates broker-side SL/TP.

If the fill is already beyond structural invalidation, actual risk exceeds the configured tolerance, or protection cannot be confirmed, the worker attempts an **emergency close** rather than widening the stop.

## 9. EXIT safety and authority

The current strategy has no discretionary early-exit rule: it exits by the structural stop or fixed 2R target. Both are installed directly on the MT5 position. Therefore:

- broker-side MT5 SL/TP is authoritative for protective exits;
- `EXECUTE_TRADINGVIEW_EXIT_ALERTS=false` by default;
- a TradingView simulated EXIT alert is recorded/reconciled but does not close an otherwise valid MT5 position;
- if the broker already closed the position, the TradingView EXIT is a no-op;
- no EXIT handler can intentionally open an opposite position.

The advanced opt-in switch is not needed for this strategy. If deliberately enabled, it can only close the exact side and trade-identity comment associated with the event. Late exits, other chart instances and broker-modified/unrecognized comments do not authorize closing a different trade.

## 10. Restart/recovery

Accepted webhooks are durable in SQLite before the server acknowledges them. Events are idempotent by `event_id`.

An unknown broker outcome is **not** retried automatically. The worker first reconciles whether a matching MT5 position exists. If the process stops while an event is marked `PROCESSING`, the next worker start moves that event to `RECONCILIATION_REQUIRED` instead of resending it. Inspect MT5 account state and the event record before any manual retry.

Unresolved events persist an entry pause shared by every chart instance feeding this database. Broker protection remains active, and informational exits can still be processed. Run only one service/database for one broker account, with one magic number; a file lease prevents a second worker for that database. Different hosts/databases are not an account-wide coordinator and are unsupported for concurrent trading of the same account.

Recovery is local and never sends orders:

```powershell
python -m automation.recovery
```

To resume: stop the service, inspect the actual demo account's positions, pending orders and deal history against the uncertain event, and resolve any residual/unprotected exposure in MT5. Then acknowledge that review locally:

```powershell
python -m automation.recovery --resume --broker-reviewed
```

The command pins the expected demo account, checks existing bot positions for protection and clears only the entry pause. It never requeues quarantined events or repeats an order. Restart the service after it succeeds. If the broker strips position comments, automated trade matching fails closed and requires this operator review.

This deliberately favors avoiding duplicate exposure over automatic retry.

## 11. Live trading remains disabled

The current handoff is demo-first. Keep:

```text
LIVE_TRADING_ENABLED=false
```

A real account is outside the current activation state even if the software contains the live-mode gate. Live activation requires a separate explicit approval after successful end-to-end demo verification.
