# TradingView setup

## 1. Add the strategy

On Windows, `COPY_STRATEGY.cmd` copies the complete final source to the clipboard. Paste it in Pine Editor, save and add to the chart.

1. Obtain `pine/rsi_trend_strategy.pine` from the feature branch on GitHub (or from the source package until GitHub upload succeeds). Open the file and use **Raw**, then copy its whole contents.
2. Open a **standard Candles/Bars/Line** chart, not Heikin Ashi, Renko, Kagi, Line Break or Point & Figure.
3. Set the chart to **5 minutes**.
4. Open Pine Editor and paste `pine/rsi_trend_strategy.pine`.
5. Save, compile, and add it to the chart.
6. If TradingView reports a compiler error, copy the exact error and line number before changing strategy logic.

The script itself blocks entries on unsupported chart types or non-M5 timeframes.

## 2. Inputs

Use the user-confirmed RSI settings and the remaining provisional structure defaults:

- RSI length: **9**, confirmed by the user's setup screenshot.
- RSI source: close.
- Swing confirmation: 2 left / 2 right.
- Stop buffer: 1 tick.
- Simulation risk: 1%.
- Sudden-move ATR label: 1.5 × ATR(14).
- Instance ID: give each chart a unique value, e.g. `GBPUSD-M5-DEMO-1`.

For an existing chart instance, open the **strategy** settings and explicitly change RSI length to 9; saved inputs can retain 14 after source updates. Leave the separate built-in RSI at 9 Close with SMA smoothing length 14. SMA smoothing is not used for strategy entries.

Entry simulation starts disabled through the **I verified a linear contract and quantity settings** input. Review the exact feed's point value, quantity unit/min/max/step and account-currency conversion, then enable that input. Signals/diagnostics remain visible while it is false. Inverse/nonlinear contracts do not become supported merely by checking the box.

Keep **On order fill** enabled, **On every tick** disabled, and **Fill orders on bar close** enabled as supplied. Fill recalculations update protection only; at most one confirmed-bar decision can create an entry. Changing these settings needs renewed validation and a recreated alert. Verify nonzero slippage tests, not just zero-cost close fills.

Set commission/slippage in Strategy Properties to match the feed/account being evaluated. Do not compare performance across different feeds/cost assumptions as if they were identical.

## 3. Read diagnostics before creating an alert

The top-right table reports the frozen last confirmed decision, including its UTC candle opening time. The separate RSI may display a developing bar; compare the same historical candle for parity. The table shows:

- chart validation;
- structural market state;
- RSI;
- current block/entry reason;
- latest confirmed swing high/low;
- active stop/target;
- gate counters.

A rare-trade result is not permission to relax the RSI thresholds.

The lower-left feed panel displays the exact chart ticker, feed point value,
minimum quantity, quote currency/tick, configured quantity limits and the
contract-confirmation status. Send this panel when reviewing a new instrument.
Its minimum quantity does not prove the exchange's quantity step or maximum,
and chart metadata does not establish the equivalent MT5 broker contract.

### Inspect an earlier candle (v1.4)

The tables show the most recent script calculation, not the candle under the cursor. Open TradingView's **Data Window** and hover over the historical candle to read the strategy's **Decision RSI**, **Decision trend**, **Decision swing high/low** and **Decision RSI pair**. These plots only appear in the Data Window; they do not change orders or the price scale. Keep Show diagnostics enabled.

| Field | Meaning |
|---|---|
| Decision trend | 1 bullish, -1 bearish, 2 range, 0 unknown/broken structure |
| Decision RSI pair | 1 bullish RSI <15, -1 bearish RSI >85, 0 neither |
| Unavailable values | No confirmed decision snapshot on that bar; do not infer a gate result |

The pair is an entry prerequisite, not an order/fill: position, latch, stop and sizing guards still apply. Snapshots are taken before entry/latch updates and retained across fill recalculations. Hover at the photographed dip and provide the Data Window with symbol, timeframe, date/time and built-in RSI values visible. This tests the same chart/feed rather than aligning uncertain broker-export timestamps.

## 4. Create the execution alert

TradingView does not let Pine code create a running alert. Create it manually from the chart:

1. Add the strategy to the M5 chart.
2. Click **Create Alert**.
3. Condition: choose the strategy.
4. Choose **Order fills only**.
5. Message: `{{strategy.order.alert_message}}`.
6. Webhook URL: `https://YOUR-HTTPS-HOST/tradingview/YOUR_LONG_WEBHOOK_TOKEN`.
7. Save the alert.

Use **Order fills only**, not “Order fills and alert() calls”. ENTRY fills are execution commands. Protective EXIT fills are useful audit events, while MT5's broker-side SL/TP is authoritative for the actual protected exit by default.

TradingView snapshots the script, inputs, symbol and timeframe when the alert is created. After changing the Pine script or its inputs, delete/recreate the running alert.

The strategy deliberately uses `process_orders_on_close=true` so its simulated market entry can fill on the confirmed signal bar's close. TradingView documents that this can differ from real-world execution, especially around session boundaries; MT5 therefore recalculates position risk and the 2R target from the actual broker fill instead of trusting the simulated fill price.

The event's `signal_price` is the confirmed signal-bar close, not a simulated or MT5 fill. `signal_time_ms` is that decision bar's UTC close in milliseconds, retained with the trade identity on EXIT events. Entry `planned_target` describes the pre-fill bracket; protective EXIT events carry the bracket after simulated-fill correction. The gateway never sizes an MT5 order from TradingView's simulated quantity. See [webhook schema and examples](webhooks.md).

## 5. Webhook operational constraints

Current TradingView documentation says webhook requests support ports 80/443 and are cancelled when the remote server takes longer than about three seconds. The included gateway therefore writes the event to SQLite before acknowledging it, while broker processing happens in a separate worker.

TradingView also requires 2-factor authentication for webhook alerts.

## 6. Disable the system

Fastest entry stop:

- set `NEW_ENTRIES_ENABLED=false` in the execution service and restart it;
- or disable the TradingView alert.

Existing broker-side SL/TP protection is not removed when new entries are paused.
