from __future__ import annotations

from dataclasses import replace
import time

from automation.broker import AccountSnapshot, OrderResult, PositionSnapshot, SymbolSnapshot


class FakeBroker:
    def __init__(self):
        self.connected = False
        self.closed = False
        self.account_snapshot = AccountSnapshot(
            is_demo=True,
            equity=10_000.0,
            margin_free=9_000.0,
            currency="USD",
            trade_allowed=True,
            trade_expert=True,
            login=100000,
            server="Fake-Demo",
        )
        self.symbols = {
            "GBPUSD": SymbolSnapshot("GBPUSD", 0.00001, 0.00001, 5, 0.01, 100.0, 0.01, 1.25000, 1.25010),
            "XAUUSD": SymbolSnapshot("XAUUSD", 0.01, 0.01, 2, 0.01, 100.0, 0.01, 2500.00, 2500.20),
            "US30.cash": SymbolSnapshot("US30.cash", 0.01, 0.01, 2, 0.01, 100.0, 0.01, 45000.0, 45001.0),
            "BTCUSD": SymbolSnapshot("BTCUSD", 0.01, 0.01, 2, 0.01, 100.0, 0.01, 100000.0, 100010.0),
        }
        self._positions: list[PositionSnapshot] = []
        for symbol in self.symbols.values():
            symbol.quote_time_ms = int(time.time() * 1000)
        self.next_ticket = 1001
        self.open_result_ok = True
        self.open_result_uncertain = False
        self.uncertain_creates_position = False
        self.protection_result_ok = True
        self.close_result_ok = True
        self.force_fill_price: float | None = None
        self.protection_calls = 0
        self.close_calls = 0
        self.open_calls = 0

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True

    def account(self):
        return self.account_snapshot

    def symbol(self, name: str):
        return self.symbols[name]

    def positions(self, symbol=None, magic=None):
        out = self._positions
        if symbol is not None:
            out = [p for p in out if p.symbol == symbol]
        if magic is not None:
            out = [p for p in out if p.magic == magic]
        return list(out)

    def risk_for_one_lot(self, side, symbol, entry, stop):
        # Deterministic fake: $100,000 per full price unit for 1 lot on FX,
        # and $1 per point on the other example symbols.
        factor = 100000.0 if symbol == "GBPUSD" else 1.0
        return abs(entry - stop) * factor

    def required_margin(self, side, symbol, volume, entry):
        return 100.0 * volume

    def open_market(self, *, side, symbol, volume, sl, tp, magic, deviation_points, comment):
        self.open_calls += 1
        if not self.open_result_ok and not self.open_result_uncertain:
            return OrderResult(ok=False, retcode=10030, message="fake rejection")
        snap = self.symbols[symbol]
        fill = self.force_fill_price if self.force_fill_price is not None else (snap.ask if side == "LONG" else snap.bid)
        pos = PositionSnapshot(
            ticket=self.next_ticket,
            symbol=symbol,
            side=side,
            volume=volume,
            price_open=fill,
            sl=sl,
            tp=tp,
            magic=magic,
            comment=comment,
        )
        self.next_ticket += 1
        if self.open_result_uncertain:
            if self.uncertain_creates_position:
                self._positions.append(pos)
            return OrderResult(ok=False, retcode=10012, message="fake timeout", uncertain=True)
        self._positions.append(pos)
        return OrderResult(ok=True, order_ticket=pos.ticket, deal_ticket=pos.ticket + 10_000, retcode=10009, message="done")

    def set_protection(self, *, position_ticket, symbol, sl, tp):
        self.protection_calls += 1
        if not self.protection_result_ok:
            return OrderResult(ok=False, message="fake protection failure")
        for i, p in enumerate(self._positions):
            if p.ticket == position_ticket:
                self._positions[i] = replace(p, sl=sl, tp=tp)
                return OrderResult(ok=True, retcode=10009, message="done")
        return OrderResult(ok=False, message="position missing")

    def close_position(self, *, position, deviation_points, comment):
        self.close_calls += 1
        if not self.close_result_ok:
            return OrderResult(ok=False, message="fake close failure")
        self._positions = [p for p in self._positions if p.ticket != position.ticket]
        return OrderResult(ok=True, retcode=10009, message="done")
