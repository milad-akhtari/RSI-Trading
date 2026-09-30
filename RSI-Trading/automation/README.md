# External execution service

The service receives TradingView strategy **order-fill** events and executes them through the official MetaTrader5 Python integration.

Safety properties:

- durable SQLite event record before HTTP acknowledgement;
- event-id deduplication;
- M5-only webhook validation;
- symbol map + allowlist;
- demo-account enforcement in demo mode;
- new-entry kill switch independent from exits;
- account-wide position/risk caps;
- broker contract-aware sizing using `order_calc_profit()` and volume steps;
- market order submitted with protective SL/TP;
- broker tick-size normalization, reconciliation and 2R target correction from actual fill;
- emergency close if structural protection becomes invalid/unavailable;
- broker-side MT5 SL/TP is authoritative for v1 exits; TradingView simulated EXIT alerts are informational by default;
- no blind automatic retry after unknown broker outcome or interrupted worker processing;
- live trading disabled until explicit future approval.

See `docs/mt5-setup.md`.
