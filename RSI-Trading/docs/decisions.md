# Decision log

## Explicit / user-authorized

- Name: RSI Trend Strategy.
- RSI 9 Close: confirmed by the setup screenshot supplied September 30; Pine v1.3 corrects the former 14-period default. Separate SMA 14 remains a display line.
- Standard M5 chart only.
- User confirmed bullish higher highs + higher lows and bearish lower lows + lower highs on September 30.
- User confirmed option B: a confirmed M5 close below the latest higher low breaks bullish structure and blocks a new BUY even with RSI <15.
- BUY: bullish structural trend + RSI < 15.
- SELL: bearish structural trend + RSI > 85.
- Range: no new entry.
- Exact boundaries are strict: 15 blocks BUY; 85 blocks SELL; 90 is eligible SELL but not `>90` stronger.
- Gross target: 2R from the initial structural stop.
- No higher/lower timeframe confirmation.
- MetaTrader 5 is the first execution target.
- Complete execution integration is required; alert-only is not complete.
- Live trading remains disabled until the user explicitly approves it after demo verification.

## v1 engineering definitions selected after source review

These are deliberately configurable and are not presented as facts about the user's historical TradingView settings:

- Earlier RSI 14 default was provisional; superseded by user-confirmed RSI 9 Close on September 30.
- Swing selection remains a provisional 2-left / 2-right confirmed pivot rule. User confirmed HH+HL bullish and LL+LH bearish; this does not approve pivot sensitivity, equal/conflicting handling or reset/re-establishment parameters.
- Entry: confirmed M5 bar close; market order processed on close.
- Repeat-entry lock: one entry per continuous qualifying RSI extreme; re-arm only after the threshold is left.
- Stop: latest confirmed structural swing plus 1 tick outward buffer.
- Sudden-move diagnostic: countertrend candle body >= 1.5 × ATR(14); quality label only.
- Pine simulation risk default: 1% of equity, configurable.
- MT5 runtime safety defaults: max 1% new-trade risk, 2% total bot stop-risk, 1 bot position, new entries disabled until the demo setup is deliberately armed.

## Autonomous finalization, September 30

The user requested the final product without additional manual chart work. Retain the documented 2/2 confirmed pivots, equal/conflict handling, symmetric bearish break, gap resets and fresh-pivot re-establishment as explicit engineering defaults. They are not source-confirmed historical parameters. The selected chart candle has matching low RSI but BEARISH state; do not force a BUY or change strict thresholds. The software handoff is complete with order submission disabled; external Windows/TradingView/order verification is separately identified.

## TradingView execution settings

- `calc_on_every_tick = false`
- `calc_on_order_fills = true` in v1.1, for protection only
- `process_orders_on_close = true`
- `pyramiding = 0`

Confirmed M5 closes create entries. Fill recalculations are detected from position/closed-trade changes and cannot create entries, update pivots, reset an extreme or increment signal gates. The first fill recalculation freezes a 2R target from `strategy.position_avg_price`, including simulated slippage. A protective bracket is also seeded with the entry command. These guards require real TradingView verification; static Python checks do not prove Pine runtime behavior.

v1.1 fixes trade identity to chart instance + feed + direction + decision-bar close time, independent of a historical trade counter. A confirmed close beyond the latest supporting structural swing, or a gap of more than five minutes between chart bars, clears the structure. Two fresh highs and lows must then be confirmed. The bullish close-break rule is now user-confirmed. Bearish symmetry, gap resets and the exact re-establishment/pivot rules remain provisional engineering choices.

Simulation quantities require confirmation of the exact linear contract, quantity increments and feed metadata. The default confirmation input is false; candidate signals still display. Currency conversion affects sizing only, never signal confirmation. Nonlinear/inverse contracts are unsupported by the Pine sizing formula.

Execution additions: pin the selected MT5 login/server; reject stale quotes and future entry timestamps; use FOK/IOC for market orders so no RETURN remainder can remain active; verify exact protection prices; verify an emergency close removed the whole ticket. Unknown outcomes persist an account-wide entry pause in the shared event database. One worker is allowed per database. Separate services/databases must not trade the same account.

## External event stream

TradingView integration uses **strategy order-fill alerts only**, via `{{strategy.order.alert_message}}`; setup alerts are not execution commands.

For entries, the TradingView **ENTRY order-fill event** is the authoritative command to the execution service. After MT5 fills it, MT5 becomes authoritative for actual fill, volume, position state and protection. For this strategy's only exits (structural stop and fixed 2R target), the **broker-side MT5 SL/TP is authoritative**. TradingView simulated EXIT order-fill events are accepted for reconciliation but do not close an MT5 position by default (`EXECUTE_TRADINGVIEW_EXIT_ALERTS=false`).

The service is idempotent by `event_id`. It never treats both a setup alert and an order-fill alert as separate entry commands.

## Still requires user-side account setup, not strategy redesign

- Connect a real MT5 **demo** account in the Windows terminal.
- Confirm its exact server and symbol names.
- Enter the original RSI length/source if different from the v1 defaults.
- Compile the Pine script in TradingView and create the webhook alert.
- Run an end-to-end demo order before any discussion of live activation.
