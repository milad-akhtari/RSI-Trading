# RSI Trend Strategy — executable specification

Status: **v1 implementation specification**. The user's explicit RSI rules are authoritative. Where the source files do not contain a machine-readable definition, v1 uses a transparent, configurable engineering definition rather than pretending the missing detail was supplied.

## 1. Non-negotiable strategy rules

Source: `RSI_TradingView_GitHub_Master_Prompt.txt`, section **MY STRATEGY: NON-NEGOTIABLE BASELINE**.

- Strategy name: **RSI Trend Strategy**.
- Signals are calculated from the chart's **standard 5-minute bars only**.
- Ranging market: **no new entry**.
- BUY candidate: established bullish trend **and RSI < 15**.
- SELL candidate: established bearish trend **and RSI > 85**.
- RSI exactly 15 does not qualify for BUY.
- RSI exactly 85 does not qualify for SELL.
- RSI exactly 90 qualifies for SELL but is not in the `> 90` stronger label.
- RSI 20–80 is no trade, and 15–20 / 80–85 also fail the actual entry thresholds.
- Sudden countertrend movement is a **quality attribute**, not a required gate.
- Planned gross reward-to-risk: **1:2**.
- No higher- or lower-timeframe confirmation is used.
- No RSI-based exit, breakeven, trailing stop, partial profit, martingale, grid, averaging down, or automatic reversal is added.

## 2. RSI implementation

The setup screenshot supplied by the user on 2026-09-30 confirms the RSI settings. Pine v1.3 corrects the earlier engineering default of 14:

- Calculation: TradingView `ta.rsi()`.
- Default length: **9**, confirmed in the user's setup screenshot.
- Default source: **close**, selectable among the chart's own OHLC/HL2/HLC3/OHLC4 values. Other indicator sources cannot be imported.
- Entry value: RSI itself, without extra smoothing. The separate built-in indicator's **SMA 14** is an additional display line, not the RSI length or an added entry condition.
- Indicator timeframe: chart; wait for timeframe closes enabled. Strategy entries continue to evaluate confirmed M5 closes.

Existing chart instances can retain saved inputs; set RSI length to 9 explicitly. Manual trend rules remain subject to validation.

## 3. Structural trend / range translation

Supporting source: `Trading Psychology and Introduction to Financial Markets.docx` repeatedly describes bullish structure with **higher highs + higher lows** and bearish structure with **lower highs + lower lows**, and distinguishes a pullback from a full reversal. The educational source is context only; it does not specify a Pine pivot length.

Deterministic v1 translation on M5:

1. Confirm swing highs and lows with `ta.pivothigh()` / `ta.pivotlow()`.
2. Default pivot confirmation: **2 bars left + 2 bars right** (configurable).
3. A pivot is not usable until the right-side confirmation bars have closed. No signal is back-dated to the visual pivot bar.
4. Bullish = last confirmed swing high > previous confirmed swing high **and** last confirmed swing low > previous confirmed swing low.
5. Bearish = last confirmed swing high < previous confirmed swing high **and** last confirmed swing low < previous confirmed swing low.
6. If swings are unavailable, state = `UNKNOWN` and entries are blocked.
7. Equal or conflicting swing progression = `RANGE` and entries are blocked.
8. Latest candle direction and RSI do not define trend. A bearish M5 pullback can exist inside a bullish HH/HL structure, and vice versa.
9. A confirmed close strictly below the latest supporting bullish swing low, or above the latest supporting bearish swing high, invalidates the structure. A candle moving against the trend without this break does not invalidate it.
10. Invalidation or a gap greater than five minutes clears all four swings. Re-establishment requires two fresh confirmed highs and two fresh confirmed lows whose origins are after the reset bar. Equality at a supporting swing is not itself a break; equal swing progression still blocks trend classification.

The user confirmed HH+HL bullish, LL+LH bearish, and the bullish close-break rule on September 30. This confirmation does not establish the pivot length, treatment of equal/conflicting swings, gap resets or fresh-pivot re-establishment rule. Those remain provisional and need comparison with the user's marked trade example.

## 4. Entry timing and repeat-entry policy

The source does not establish whether the user's historical TradingView signals used intrabar RSI. v1 chooses reproducibility:

- `calc_on_every_tick = false`.
- Signals are evaluated on **confirmed M5 bar close**.
- `process_orders_on_close = true`, so the TradingView strategy emulator can fill the market entry on the signal bar's closing tick rather than waiting for the next M5 bar.
- `calc_on_order_fills = true`, restricted to protection and trade-state cleanup. Signals, pivot updates and re-arming are gated by `evaluateSignal`, which excludes detected fill recalculations and permits at most one decision per bar.
- One position at a time; `pyramiding = 0`.
- No automatic reversal while a position is open.
- A persistent RSI extreme can trigger only once. After a BUY, long entries re-arm only after RSI returns to `>= 15`; after a SELL, short entries re-arm only after RSI returns to `<= 85`.

The reset rule prevents duplicate entries from one long-lasting extreme. It does not change the actual entry thresholds and does not wait for RSI to cross *back out* before the first entry.

## 5. Stop and target

Supporting source: the educational document repeatedly states that a stop belongs beyond the structural point whose break invalidates the trade, not at an arbitrary dollar distance.

v1:

- BUY stop: latest confirmed structural swing low minus a configurable tick buffer (default 1 tick).
- SELL stop: latest confirmed structural swing high plus a configurable tick buffer (default 1 tick).
- A stop on the wrong side of the intended entry invalidates the setup.
- BUY: `R = entry - stop`; `target = entry + 2R`.
- SELL: `R = stop - entry`; `target = entry - 2R`.
- Stops are rounded outward and targets are rounded outward to valid TradingView tick increments so quantization does not intentionally reduce the structural stop or the intended 2R reward.
- Stop is never widened after entry to preserve a nominal ratio.
- The entry command seeds the bracket at once. On the first fill recalculation, the target is corrected once using the actual simulated average fill. Later structure/ATR/RSI changes cannot move the bracket. An invalid fill stop or fill risk above its configured tolerance triggers an immediate close-only safety exit.
- Historical same-bar stop/target ambiguity remains subject to TradingView's emulator path. No lower-timeframe Bar Magnifier or signal confirmation is used in the baseline.

In MT5, the execution service first normalizes the structural stop to the broker's `trade_tick_size`, then recalculates the final 2R target from the **actual broker fill** while keeping that normalized structural stop. Volume is sized from the normalized stop. If a gap puts the fill beyond structural invalidation, the position is emergency-closed rather than inventing a wider stop.

The MT5 broker-side SL/TP is authoritative for the current strategy's protective exit. TradingView's simulated bracket EXIT alert is retained for audit/reconciliation, but it does not close a valid MT5 position by default because TradingView and MT5 fills/feeds can differ.

## 6. Position sizing

The files do not establish the user's personal fixed risk percentage for this strategy. The course contains example risk frameworks, but those are not adopted as the user's rule.

- Pine simulation default: **1.0% of strategy equity**, configurable.
- This is an engineering/safety default, not a claim about the user's historical risk.
- Pine simulation sizing uses stop distance and `syminfo.pointvalue`, converts instrument-currency loss to the declared USD strategy account, and rounds the capped quantity down to its step. Overrides are exposed for verified contracts. `linearContractVerified=false` blocks entry orders until the exact quantity/contract metadata is checked.
- MT5 is authoritative for live/demo sizing. It uses the broker's current account equity, `order_calc_profit()` for one-lot loss at the stop, and the broker's `volume_min`, `volume_max`, and `volume_step`.
- MT5 volume is rounded **down** to avoid intentionally exceeding the risk budget.
- Default execution caps: 1% max per entry, 2% total bot stop-risk, and 1 simultaneous bot position. These are configurable safety caps, not strategy alpha.
- Actual MT5 fill risk must also obey the hard per-entry and total risk caps; the fill-overrun tolerance does not override those caps. Costs, gaps, stop execution and financing can still change realized net risk.
- All chart instances use one gateway/database/worker and one bot magic number for an account. These caps cover that shared bot service; unrelated manual positions and separate services are not coordinated. An existing position of any origin on the proposed symbol prevents entry to avoid netting/reversal.

## Parameter register

All numeric defaults below are engineering choices under the user's instruction to proceed, except fixed M5, strict thresholds and 2R, which are explicit strategy rules.

| Parameter | Unit and allowed range | Default / status |
|---|---|---|
| Timeframe and chart | standard time-based chart | M5 fixed, explicit |
| RSI | `ta.rsi`, length >=2, chart price source only | 9, Close, no extra smoothing |
| Entry thresholds | RSI units | BUY <15, SELL >85, strength >90, explicit |
| Pivots | bars on each side, 1..20 | 2 left / 2 right |
| Invalidation | confirmed close / time gap | strict supporting-swing break; gap >300 seconds |
| Stop buffer | ticks, 0..1000 | 1 outward |
| Target | gross R multiple | 2 fixed, explicit |
| Simulation account | USD, initial capital in Strategy Properties | 10,000; never the MT5 account balance |
| Simulation stop risk | equity %, 0.01..5 | 1 |
| Linear contract confirmation | boolean | false until feed/units checked |
| Quantity step / min / max | contract quantity, >0; max >= min | 0.01 / 0.01 / 1,000,000; require feed verification |
| Point value override | instrument currency per full point per unit, >=0 | 0 uses feed metadata |
| Simulation fill tolerance | % over original budget, 0..100 | 10; close-only rescue above it |
| Quality label | ATR length >=2, body multiple >=0.1 | ATR(14), 1.5; never an entry gate |
| Instance ID | nonempty string, <=80 characters | RSI-M5-DEMO-1; make each chart unique |
| MT5 entry / total bot risk | equity %, (0,5] / (0,100] | 1 / 2 |
| MT5 positions | count >=1 | 1 |
| Free-margin fraction | (0,1] | 0.5 |
| Event age / future skew | seconds, >0 / >=0 | 120 / 10 |
| Quote age | seconds, >0 | 30 |
| MT5 fill tolerance | % over budget, >=0 | 10; hard risk caps also apply |
| Spread / deviation | broker points, >0 / >=0 | 1,000,000 / 20; set per selected contract before arming |
| Reconciliation window | seconds, >=0 | 2 |
| Submission / live / new entries | booleans | false / false / false |
| Expected MT5 account | exact login and server strings | unset; required to arm submission |
| Feed-to-symbol mapping | exact allowlisted ticker -> broker symbol | examples only, require verification |

No session restriction or daily loss limit was supplied. v1 does not invent one. Trading occurs on available M5 bars after sufficient structure; broker session/rejection checks still apply. No prop-firm compliance is claimed.

## 7. Sudden countertrend movement

There is a real source tension:

- The user's explicit strategy says a sudden upward move inside a bearish trend can make an RSI > 85 SELL setup stronger, and a sudden downward move inside a bullish trend can make an RSI < 15 BUY setup stronger.
- The course also contains a general principle warning against blindly trading against a genuine spike.

v1 does **not** resolve that tension by blocking entries. Sudden movement remains informational only. For a measurable chart label, v1 tags a countertrend M5 candle as `SUDDEN_COUNTERTREND` when its body is at least **1.5 × ATR(14)**. That numerical definition is an engineering diagnostic, not a required condition and not evidence of a higher win probability.

## 8. Event precedence

1. Existing broker-side protection / exits remain active regardless of new-entry gates.
2. Unsupported chart/timeframe -> no new Pine entry.
3. `UNKNOWN` or `RANGE` -> no new entry.
4. Existing Pine position -> no new entry.
5. RSI threshold + trend eligibility must pass.
6. Extreme episode must be armed.
7. Structural stop must be valid.
8. Simulation sizing must be valid.
9. Entry + protective bracket are submitted.
10. External MT5 service separately validates freshness, symbol mapping, demo-account status, account-wide caps, spread, margin, broker sizing, and protection.
