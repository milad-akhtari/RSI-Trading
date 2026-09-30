# Source review and conflict audit

## Source priority used

1. User's explicit RSI Trend Strategy and later clarifications.
2. Implementation definitions selected transparently for v1.
3. Educational material and historical FTMO examples.

No educational setup has been imported as a new strategy filter.

## Explicit strategy evidence

`RSI_TradingView_GitHub_Master_Prompt.txt`, **MY STRATEGY: NON-NEGOTIABLE BASELINE** supplies:

- M5 only.
- Range = no trade.
- Bearish + RSI > 85 = SELL candidate; > 90 is a stronger label.
- Bullish + RSI < 15 = BUY candidate; lower values are qualitatively stronger.
- 20–80 = no trade, without authorizing the threshold gaps.
- Sudden countertrend moves may strengthen a setup.
- Planned R:R = 1:2.
- No other timeframe for confirmation.
- Target markets: Bitcoin, Gold, US30 and forex.

The same file explicitly warns not to infer an unseen RSI period, not to silently add divergence/order-block/MTF logic, not to treat FTMO fields as proof of the original stop, and not to call an alert-only script an end-to-end bot.

## Educational material used as implementation context

Targeted review of `Trading Psychology and Introduction to Financial Markets.docx` found the following relevant ideas:

- **Session 8, sections 3-10:** HH/HL bullish, LH/LL bearish, ranges, structured moves versus spikes, and weak/strong trend descriptions inform the structural proposal. They do not specify pivot confirmation lengths.
- **Trend/momentum sections:** a bullish structural trend can coexist with a bearish correction and a bearish structural trend can coexist with a bullish correction. This supports keeping structural trend separate from current candle/RSI momentum.
- **Session 8, section 13, Trading During a Spike:** the course warns against trading blindly against a genuine spike.
- **Liquidity / stop-placement sections:** the stop belongs where the trade thesis becomes structurally invalid; a hard stop is safer than removing protection because of “stop hunting.”
- **Stop Loss Must Be Defined Before Entry** and **Position Size:** the technical invalidation/stop comes first, then position size. Numerical course examples are not adopted as the user's account rules.

Important limitation: the course discusses many additional tools—higher timeframes, divergence, supply/demand, Miner entries, ACD, liquidity sweeps and alternate exit systems. They are **not** part of this RSI implementation unless the user explicitly adds them later.

## Historical FTMO material

The Account Analysis and individual Trade Reports are treated as historical examples only. They show actual historical symbols, sizes, entry/close fields and reported P&L, but do not provide the missing RSI configuration or a complete deterministic entry specification.

Examples include BTCUSD, US30.cash and GBPUSD trades. The chart screenshots extracted from `trading files.zip` display **1-minute** chart headers (`1m`, symbol `· 1 · MT5`) across the supplied US30.cash, GBPUSD and BTCUSD images. Therefore those screenshots cannot be used as proof that the original decision timeframe was M5. The explicit written M5 rule remains authoritative.

The FTMO report itself also states that its account analysis is automated/statistical and is not an investment recommendation or proof of strategy compliance/performance.

## Source conflict retained rather than hidden

The educational material's general “do not trade against a spike” rule conflicts with the user's explicit statement that sudden countertrend movement *inside an established trend* can strengthen the RSI reversion setup.

v1 preserves the user's explicit strategy. It does **not** add a blanket spike-rejection filter. “Sudden movement” is only a diagnostic strength label and cannot change risk, add positions, or reject a baseline setup.

## Gaps the files do not actually answer

The files do not establish with confidence:

- the exact historical RSI period/source/smoothing in the user's TradingView workspace;
- a numeric swing/pivot confirmation length;
- the user's personal risk percentage for this exact system;
- the exact TradingView data-feed tickers that will be paired with the MT5 broker symbols;
- the user's MT5 demo server/account details.

v1 therefore keeps these as visible configuration rather than presenting guesses as historical facts.

## Review scope and evidence limits

The supplied set contains the master prompt, a long educational DOCX, one Account Analysis PDF (13 pages), eleven Trade Report PDFs (3 pages each), and `trading files.zip` with eleven JPEG chart screenshots. All eleven chart images were visually inspected together, with their displayed 1-minute interval checked. The trade-report text was extracted, and selected report pages were rendered to check what the exports contain. Educational review was targeted to the headings above, not claimed as exhaustive review of every course section.

`Account Analysis _ FTMO.pdf`, page 1 describes its automated/statistical nature. The individual `Trade Report _ FTMO*.pdf` exports show trade/protection/result fields on page 2 and export metadata/footer on pages 1-3. Export dates are not trade dates; displayed stop fields are not proof of the original entry stop, and closes are not proof of a planned initial 2R target. The original RSI pane/settings are absent from the screenshots. No historical example has been labelled by the user as an acceptance fixture for the exact automated rules.

`fomop.zip` and a separately named `Market Strategy` resource were not supplied under those names. The available `trading files.zip` was reviewed directly; it is not silently renamed or claimed to be the missing archive. No raw educational files, screenshots, account reports or identifiers are included in Git.

The user's later instruction to read the files, decide what is needed and proceed authorizes the visible engineering choices. It does not make those choices historical facts or authorize live activation.

Official references checked on 2026-09-29:

- [TradingView strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/): confirmed execution, fill recalculation, emulator assumptions, slippage and account-currency conversion.
- [TradingView alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/): strategy order-fill messages and recreated alert snapshots.
- [TradingView webhooks](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/): HTTPS ports, timeout and delivery limits.
- [MetaQuotes order submission](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py), [profit calculation](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py) and [fill policies](https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties): contract-aware monetary risk and order-result handling.
