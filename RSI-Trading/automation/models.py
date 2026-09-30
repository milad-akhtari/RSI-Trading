from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class WebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0", "1.1"]
    strategy: Literal["RSI Trend Strategy"]
    instance_id: str = Field(min_length=1, max_length=80)
    event_id: str = Field(min_length=8, max_length=400)
    event_type: EventType
    side: Side
    ticker: str = Field(min_length=1, max_length=120)
    timeframe: str
    signal_time_ms: int = Field(gt=0)
    signal_price: float = Field(gt=0)
    structural_stop: float = Field(gt=0)
    planned_target: float | None = Field(default=None, gt=0)
    rr: float = Field(gt=0, le=10)
    risk_pct: float = Field(gt=0, le=5)
    rsi: float = Field(ge=0, le=100)
    market_state: Literal["BULLISH", "BEARISH", "RANGE", "UNKNOWN"]
    strength: str = Field(min_length=1, max_length=80)
    trade_id: str = Field(min_length=1, max_length=120)
    chart_tick_size: float | None = Field(default=None, gt=0)

    @field_validator("timeframe")
    @classmethod
    def require_m5(cls, value: str) -> str:
        if value != "5":
            raise ValueError("Only TradingView 5-minute events are accepted")
        return value

    @model_validator(mode="after")
    def strategy_contract_is_coherent(self) -> "WebhookEvent":
        # These are transport-level safety checks. The MT5 adapter validates again
        # against the broker quote, symbol increments, account state and risk limits.
        if abs(self.rr - 2.0) > 1e-9:
            raise ValueError("RSI Trend Strategy events must use rr=2.0")
        if self.schema_version == "1.1" and self.chart_tick_size is None:
            raise ValueError("Schema 1.1 requires chart_tick_size")

        if self.event_type == EventType.ENTRY:
            if self.planned_target is None:
                raise ValueError("ENTRY requires a planned_target")
            if self.side == Side.LONG:
                if self.market_state != "BULLISH" or not self.rsi < 15:
                    raise ValueError("LONG entry requires BULLISH state and RSI < 15")
                if not self.structural_stop < self.signal_price:
                    raise ValueError("LONG structural_stop must be below signal_price")
                expected_target = self.signal_price + 2.0 * (self.signal_price - self.structural_stop)
            else:
                if self.market_state != "BEARISH" or not self.rsi > 85:
                    raise ValueError("SHORT entry requires BEARISH state and RSI > 85")
                if not self.structural_stop > self.signal_price:
                    raise ValueError("SHORT structural_stop must be above signal_price")
                expected_target = self.signal_price - 2.0 * (self.structural_stop - self.signal_price)

            # Only outward rounding by at most one declared chart tick is permitted.
            # Schema 1.0 remains readable for existing alerts; 1.1 removes its ambiguous
            # price-relative rounding tolerance.
            numerical = max(abs(self.signal_price) * 1e-12, 1e-12)
            tolerance = (self.chart_tick_size or max(abs(self.signal_price) * 1e-6, 1e-9)) + numerical
            delta = self.planned_target - expected_target
            outward = delta if self.side == Side.LONG else -delta
            if outward < -numerical or outward > tolerance:
                raise ValueError("planned_target is not coherent with the declared 2R bracket")
        return self
