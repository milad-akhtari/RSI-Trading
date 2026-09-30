# Webhook contract

Use one strategy alert stream: **Order fills only** with message `{{strategy.order.alert_message}}`. ENTRY is an instruction to the gateway after a TradingView simulated fill. MT5 validates it again and sizes from its own account/quote. EXIT is informational by default because MT5's broker-side SL/TP is authoritative. No setup-alert stream submits orders.

The machine-readable schema is [webhook-schema.json](webhook-schema.json), generated from the gateway model. Pine emits schema **1.1**. Schema 1.0 remains readable for older alerts, but recreate them using 1.1 to obtain declared tick precision and stable instance-specific IDs.

| Field | Meaning |
|---|---|
| `schema_version`, `strategy` | Fixed version and strategy identity |
| `instance_id` | Unique chart/alert installation identity |
| `event_id` | Instance, exact ticker/feed, M5, direction, decision-bar close and event type |
| `trade_id` | Direction + decision-bar UTC close time; ENTRY/EXIT retain it |
| `ticker`, `timeframe` | Exact feed-qualified ticker; timeframe must be `5` |
| `signal_time_ms`, `signal_price` | Confirmed decision-bar UTC close time and price, **not broker-fill fields** |
| `side`, `market_state`, `rsi` | Original signal direction, structural classification and RSI |
| `structural_stop`, `planned_target` | Frozen stop and planned bracket; EXIT target reflects the simulated-fill adjustment. An invalid EXIT target is null. ENTRY always requires a positive target. |
| `chart_tick_size` | Required in 1.1; target may round outward by at most one tick |
| `rr`, `risk_pct` | Fixed 2R and requested monetary stop-risk %; broker caps apply independently |
| `strength` | Qualitative attribute only; no sizing/eligibility change |

Prices are serialized with sufficient decimal precision for forex and tick rounding. Strings are JSON-escaped. The gateway rejects nonfinite values, unknown fields, non-M5 events, incorrect directional thresholds and inconsistent entry brackets.

[fixtures/webhook-entry.example.json](../fixtures/webhook-entry.example.json) is a synthetic transport example. It is not a market backtest, a current signal or an instruction to trade. Its fixed timestamp deliberately becomes stale. Automated tests generate fresh synthetic events with a fake broker.

The HTTPS endpoint is `/tradingview/<private-token>`. It durably records an event before HTTP 202. Duplicate identical events return `duplicate=true`. Reusing an ID with changed content, or replaying the same logical trade under a new ID, returns 409. Unavailable/busy storage returns 503 rather than falsely acknowledging durability. The response does not mean MT5 filled an order.

Read authenticated event status at `/status/<private-token>/<event_id>`. Events progress through PENDING, PROCESSING and DONE or FAILED. Unknown/interrupted broker outcomes become RECONCILIATION_REQUIRED and persist a pause on later ENTRY events. Broker-side protection and informational EXIT processing continue. One worker/database serves all chart instances for the account.

ENTRY freshness and broker-quote freshness are checked immediately before processing. A schema-valid stale event can be recorded for audit but is rejected by the worker and submits no order. EXIT retains original signal time and is not rejected solely for age. When optional close-only EXIT handling is deliberately enabled, symbol, side, magic and trade-identity comment must all match; a late EXIT cannot close a newer trade.

Treat successful webhook delivery, TradingView's simulated fill, and MT5's actual fill as separate events. Pine receives no broker-state callbacks. Recreate running alerts after every script/input change. Keep tokens/credentials private and redact URL paths in any reverse-proxy logs.
