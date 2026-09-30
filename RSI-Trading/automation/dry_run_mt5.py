"""Synthetic sizing check using native MT5 reads; all broker writes are blocked."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
import time
import uuid

from .broker import Broker, SymbolSnapshot
from .config import Settings
from .engine import ExecutionEngine, ExecutionRejected
from .models import WebhookEvent
from .mt5_client import MT5Broker


class ReadOnlyBroker:
    """Expose only the native reads needed by the execution engine."""

    def __init__(self, broker: Broker):
        self._broker = broker
        self.last_margin = None
        self.last_symbol = None

    def connect(self):
        return self._broker.connect()

    def close(self):
        return self._broker.close()

    def account(self):
        return self._broker.account()

    def symbol(self, name):
        self.last_symbol = self._broker.symbol(name)
        return self.last_symbol

    def positions(self, symbol=None, magic=None):
        return self._broker.positions(symbol=symbol, magic=magic)

    def risk_for_one_lot(self, side, symbol, entry, stop):
        return self._broker.risk_for_one_lot(side, symbol, entry, stop)

    def required_margin(self, side, symbol, volume, entry):
        self.last_margin = self._broker.required_margin(side, symbol, volume, entry)
        return self.last_margin

    def open_market(self, **kwargs):
        raise RuntimeError("Read-only check blocks order submission")

    def set_protection(self, **kwargs):
        raise RuntimeError("Read-only check blocks protection modifications")

    def close_position(self, **kwargs):
        raise RuntimeError("Read-only check blocks position closure")


def synthetic_event(symbol: SymbolSnapshot, side: str, stop_distance: float, risk_pct: float) -> WebhookEvent:
    if side not in {"LONG", "SHORT"}:
        raise ValueError("Side must be LONG or SHORT")
    if not math.isfinite(stop_distance) or stop_distance <= 0:
        raise ValueError("Stop distance must be positive, in price units")
    entry = symbol.ask if side == "LONG" else symbol.bid
    stop = entry - stop_distance if side == "LONG" else entry + stop_distance
    target = entry + 2 * stop_distance if side == "LONG" else entry - 2 * stop_distance
    identity = uuid.uuid4().hex
    return WebhookEvent(
        schema_version="1.1", strategy="RSI Trend Strategy",
        instance_id="LOCAL-READONLY-CHECK", event_id="READONLY-" + identity,
        event_type="ENTRY", side=side, ticker="LOCALTEST:" + symbol.name,
        timeframe="5", signal_time_ms=int(time.time() * 1000),
        signal_price=entry, structural_stop=stop, planned_target=target,
        chart_tick_size=symbol.tick_size, rr=2, risk_pct=risk_pct,
        rsi=14 if side == "LONG" else 86,
        market_state="BULLISH" if side == "LONG" else "BEARISH",
        strength="SYNTHETIC_TEST_ONLY", trade_id="TEST-" + identity,
    )


def readonly_settings(settings: Settings, symbol_name: str, risk_pct: float,
                      ticker: str | None = None) -> Settings:
    # Refuse an already armed environment; never rewrite .env or gateway settings.
    if (settings.execution_mode != "demo" or settings.demo_order_submission_enabled
            or settings.live_trading_enabled or settings.execute_tradingview_exit_alerts):
        raise ValueError("Keep demo mode and all order/exit submission switches disabled before this check")
    if not symbol_name or not math.isfinite(risk_pct) or not 0 < risk_pct <= settings.max_risk_pct:
        raise ValueError("Specify a symbol and positive risk within MAX_RISK_PCT")
    safe = replace(settings, new_entries_enabled=True,
                   allowed_symbols=[symbol_name],
                   symbol_map={ticker or "LOCALTEST:" + symbol_name: symbol_name})
    safe.validate()
    return safe


def run_check(settings: Settings, broker: Broker, *, symbol_name: str, side: str,
              stop_distance: float, risk_pct: float) -> dict:
    safe = readonly_settings(settings, symbol_name, risk_pct)
    readonly = ReadOnlyBroker(broker)
    readonly.connect()
    try:
        # Reject a changed/live account before symbol calculation.
        ExecutionEngine(safe, readonly)._ensure_account_safe()
        symbol = readonly.symbol(symbol_name)
        event = synthetic_event(symbol, side, stop_distance, risk_pct)
    finally:
        readonly.close()
    result = ExecutionEngine(safe, readonly).process(event)
    if result.get("status") != "DRY_RUN_DEMO":
        raise RuntimeError("Expected a dry run; read-only adapter prevented broker writes")
    result["margin_required"] = readonly.last_margin
    return {
        "synthetic_test_only": True, "broker_writes_blocked": True,
        "settings_file_changed": False,
        "quote_clock": {
            "offset_seconds": settings.mt5_quote_time_offset_seconds,
            "offset_server": settings.mt5_quote_time_offset_server,
            "normalized_quote_time_ms": readonly.last_symbol.quote_time_ms,
        },
        "scope": "Native sizing and eligibility checks; no strategy signal, order, fill or SL/TP execution verified",
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", choices=["LONG", "SHORT"], default="LONG")
    parser.add_argument("--stop-distance", type=float, required=True,
                        help="Distance in price units: US30 100 means 100 index points")
    parser.add_argument("--risk-pct", type=float, default=1)
    parser.add_argument("--quote-time-offset-seconds", type=int, default=None,
                        help="Verified broker timestamp minus UTC, in seconds; applied in memory only")
    parser.add_argument("--quote-time-offset-server", default=None,
                        help="Exact connected server required when applying a nonzero clock offset")
    args = parser.parse_args()
    try:
        settings = Settings()
        overrides = {}
        if args.quote_time_offset_seconds is not None:
            overrides["mt5_quote_time_offset_seconds"] = args.quote_time_offset_seconds
        if args.quote_time_offset_server is not None:
            overrides["mt5_quote_time_offset_server"] = args.quote_time_offset_server
        settings = replace(settings, **overrides)
        output = run_check(settings, MT5Broker(settings), symbol_name=args.symbol,
                           side=args.side, stop_distance=args.stop_distance, risk_pct=args.risk_pct)
    except ExecutionRejected as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc), "broker_writes_blocked": True}, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "CHECK_FAILED", "reason": str(exc), "broker_writes_blocked": True}, indent=2))
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
