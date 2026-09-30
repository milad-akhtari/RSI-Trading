from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env when present. Environment variables still take precedence.
load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else int(raw)


def _csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _json_map(name: str, default: dict[str, str]) -> dict[str, str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in obj.items()):
        raise ValueError(f"{name} must be a JSON object of string-to-string mappings")
    return obj


@dataclass(frozen=True)
class Settings:
    webhook_token: str = field(default_factory=lambda: os.getenv("WEBHOOK_TOKEN", "change-me"))
    database_path: Path = field(default_factory=lambda: Path(os.getenv("DATABASE_PATH", "./data/events.sqlite3")))

    execution_mode: str = field(default_factory=lambda: os.getenv("EXECUTION_MODE", "demo").strip().lower())
    demo_order_submission_enabled: bool = field(default_factory=lambda: _bool("DEMO_ORDER_SUBMISSION_ENABLED", False))
    live_trading_enabled: bool = field(default_factory=lambda: _bool("LIVE_TRADING_ENABLED", False))
    new_entries_enabled: bool = field(default_factory=lambda: _bool("NEW_ENTRIES_ENABLED", False))
    execute_tradingview_exit_alerts: bool = field(default_factory=lambda: _bool("EXECUTE_TRADINGVIEW_EXIT_ALERTS", False))

    max_event_age_seconds: int = field(default_factory=lambda: _int("MAX_EVENT_AGE_SECONDS", 120))
    max_future_skew_seconds: int = field(default_factory=lambda: _int("MAX_FUTURE_SKEW_SECONDS", 10))
    max_quote_age_seconds: int = field(default_factory=lambda: _int("MAX_QUOTE_AGE_SECONDS", 30))
    max_risk_pct: float = field(default_factory=lambda: _float("MAX_RISK_PCT", 1.0))
    max_total_risk_pct: float = field(default_factory=lambda: _float("MAX_TOTAL_RISK_PCT", 2.0))
    max_open_positions: int = field(default_factory=lambda: _int("MAX_OPEN_POSITIONS", 1))
    max_margin_fraction: float = field(default_factory=lambda: _float("MAX_MARGIN_FRACTION", 0.50))
    max_risk_overrun_pct: float = field(default_factory=lambda: _float("MAX_RISK_OVERRUN_PCT", 10.0))
    max_spread_points: float = field(default_factory=lambda: _float("MAX_SPREAD_POINTS", 1000000.0))
    deviation_points: int = field(default_factory=lambda: _int("MT5_DEVIATION_POINTS", 20))
    mt5_magic: int = field(default_factory=lambda: _int("MT5_MAGIC", 560015))
    reconciliation_wait_seconds: float = field(default_factory=lambda: _float("RECONCILIATION_WAIT_SECONDS", 2.0))

    mt5_terminal_path: str = field(default_factory=lambda: os.getenv("MT5_TERMINAL_PATH", ""))
    mt5_login: int | None = field(default_factory=lambda: int(os.environ["MT5_LOGIN"]) if os.getenv("MT5_LOGIN") else None)
    mt5_password: str = field(default_factory=lambda: os.getenv("MT5_PASSWORD", ""))
    mt5_server: str = field(default_factory=lambda: os.getenv("MT5_SERVER", ""))
    # Explicit exception for a verified feed clock; never infer it from quote age.
    mt5_quote_time_offset_seconds: int = field(default_factory=lambda: _int("MT5_QUOTE_TIME_OFFSET_SECONDS", 0))
    mt5_quote_time_offset_server: str = field(default_factory=lambda: os.getenv("MT5_QUOTE_TIME_OFFSET_SERVER", ""))

    allowed_symbols: list[str] = field(default_factory=lambda: _csv(
        "ALLOWED_MT5_SYMBOLS", ["GBPUSD", "XAUUSD", "US30.cash", "BTCUSD"]
    ))
    symbol_map: dict[str, str] = field(default_factory=lambda: _json_map(
        "SYMBOL_MAP_JSON",
        {
            "GBPUSD": "GBPUSD",
            "FX:GBPUSD": "GBPUSD",
            "OANDA:GBPUSD": "GBPUSD",
            "XAUUSD": "XAUUSD",
            "OANDA:XAUUSD": "XAUUSD",
            "US30.cash": "US30.cash",
            "FTMO:US30.CASH": "US30.cash",
            "BTCUSD": "BTCUSD",
            "BITSTAMP:BTCUSD": "BTCUSD",
        },
    ))

    def validate(self) -> None:
        self.validate_quote_clock()
        if self.webhook_token in {"", "change-me", "replace-me", "replace-with-a-long-random-token"}:
            raise ValueError("WEBHOOK_TOKEN must be changed before starting the webhook server")
        if self.execution_mode not in {"demo", "live"}:
            raise ValueError("EXECUTION_MODE must be demo or live")
        if self.execution_mode == "live" and not self.live_trading_enabled:
            raise ValueError("Live mode is locked: LIVE_TRADING_ENABLED is false")
        numeric = [self.max_risk_pct, self.max_total_risk_pct, self.max_margin_fraction,
                   self.max_risk_overrun_pct, self.max_spread_points, self.reconciliation_wait_seconds]
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("Safety settings must be finite")
        if not 0 < self.max_risk_pct <= 5 or not 0 < self.max_total_risk_pct <= 100:
            raise ValueError("Risk caps must be within (0, 5] per entry and (0, 100] total")
        if not 0 < self.max_margin_fraction <= 1:
            raise ValueError("MAX_MARGIN_FRACTION must be within (0, 1]")
        if self.max_event_age_seconds <= 0 or self.max_quote_age_seconds <= 0 or self.max_future_skew_seconds < 0:
            raise ValueError("Event/quote age limits must be positive and future skew nonnegative")
        if self.max_spread_points <= 0 or self.max_risk_overrun_pct < 0 or self.deviation_points < 0:
            raise ValueError("Spread must be positive and risk overrun/deviation nonnegative")
        if self.max_open_positions < 1:
            raise ValueError("MAX_OPEN_POSITIONS must be at least 1")
        if self.reconciliation_wait_seconds < 0:
            raise ValueError("RECONCILIATION_WAIT_SECONDS cannot be negative")
        if self.demo_order_submission_enabled or self.execute_tradingview_exit_alerts or self.execution_mode == "live":
            if not self.mt5_login or not self.mt5_server:
                raise ValueError("Set the expected MT5_LOGIN and MT5_SERVER before enabling order submission")

    def validate_quote_clock(self) -> None:
        offset = self.mt5_quote_time_offset_seconds
        if type(offset) is not int or not -14 * 3600 <= offset <= 14 * 3600:
            raise ValueError("MT5_QUOTE_TIME_OFFSET_SECONDS must be an integer within +/-14 hours")
        if offset and not self.mt5_quote_time_offset_server.strip():
            raise ValueError("A nonzero quote clock offset requires MT5_QUOTE_TIME_OFFSET_SERVER")
