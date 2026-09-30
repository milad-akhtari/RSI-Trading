from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AccountSnapshot:
    is_demo: bool
    equity: float
    margin_free: float
    currency: str
    trade_allowed: bool
    trade_expert: bool
    login: int = 0
    server: str = ""


@dataclass
class SymbolSnapshot:
    name: str
    point: float
    tick_size: float
    digits: int
    volume_min: float
    volume_max: float
    volume_step: float
    bid: float
    ask: float
    quote_time_ms: int = 0


@dataclass
class PositionSnapshot:
    ticket: int
    symbol: str
    side: str
    volume: float
    price_open: float
    sl: float
    tp: float
    magic: int
    comment: str = ""


@dataclass
class OrderResult:
    ok: bool
    order_ticket: int | None = None
    deal_ticket: int | None = None
    retcode: int | None = None
    message: str = ""
    uncertain: bool = False


class Broker(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def account(self) -> AccountSnapshot: ...
    def symbol(self, name: str) -> SymbolSnapshot: ...
    def positions(self, symbol: str | None = None, magic: int | None = None) -> list[PositionSnapshot]: ...
    def risk_for_one_lot(self, side: str, symbol: str, entry: float, stop: float) -> float: ...
    def required_margin(self, side: str, symbol: str, volume: float, entry: float) -> float: ...
    def open_market(self, *, side: str, symbol: str, volume: float, sl: float, tp: float, magic: int, deviation_points: int, comment: str) -> OrderResult: ...
    def set_protection(self, *, position_ticket: int, symbol: str, sl: float, tp: float) -> OrderResult: ...
    def close_position(self, *, position: PositionSnapshot, deviation_points: int, comment: str) -> OrderResult: ...
