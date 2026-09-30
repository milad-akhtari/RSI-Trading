from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any

from .broker import Broker, PositionSnapshot, SymbolSnapshot
from .config import Settings
from .models import EventType, WebhookEvent


class ExecutionRejected(RuntimeError):
    pass


class ExecutionEngine:
    def __init__(self, settings: Settings, broker: Broker):
        self.settings = settings
        self.broker = broker

    @staticmethod
    def _floor_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step + 1e-12) * step

    @staticmethod
    def _floor_price(value: float, tick_size: float, digits: int) -> float:
        if tick_size <= 0:
            return round(value, digits)
        return round(math.floor(value / tick_size + 1e-12) * tick_size, digits)

    @staticmethod
    def _ceil_price(value: float, tick_size: float, digits: int) -> float:
        if tick_size <= 0:
            return round(value, digits)
        return round(math.ceil(value / tick_size - 1e-12) * tick_size, digits)

    def _normalize_stop(self, side: str, stop: float, symbol: SymbolSnapshot) -> float:
        # Round protective stops away from the entry direction so price quantization never
        # makes the stop tighter than the structural level supplied by TradingView.
        if side == "LONG":
            return self._floor_price(stop, symbol.tick_size, symbol.digits)
        return self._ceil_price(stop, symbol.tick_size, symbol.digits)

    def _map_symbol(self, ticker: str) -> str:
        symbol = self.settings.symbol_map.get(ticker)
        if not symbol:
            # Conservative fallback: only allow an already-whitelisted exact symbol.
            symbol = ticker if ticker in self.settings.allowed_symbols else ""
        if not symbol or symbol not in self.settings.allowed_symbols:
            raise ExecutionRejected(f"Ticker {ticker!r} is not mapped to an allowed MT5 symbol")
        return symbol

    def _ensure_account_safe(self) -> Any:
        account = self.broker.account()
        if not math.isfinite(account.equity) or account.equity <= 0 or not math.isfinite(account.margin_free) or account.margin_free < 0:
            raise ExecutionRejected("Invalid account equity or free margin")
        if not account.trade_allowed or not account.trade_expert:
            raise ExecutionRejected("MT5 account does not currently allow expert/API trading")
        if self.settings.execution_mode == "demo":
            if not account.is_demo:
                raise ExecutionRejected("Execution service is in demo mode but the connected MT5 account is not a demo account")
        elif self.settings.execution_mode == "live":
            if not self.settings.live_trading_enabled:
                raise ExecutionRejected("Live trading is disabled")
        if self.settings.mt5_login is not None and account.login != self.settings.mt5_login:
            raise ExecutionRejected("Connected MT5 account does not match expected MT5_LOGIN")
        if self.settings.mt5_server and account.server != self.settings.mt5_server:
            raise ExecutionRejected("Connected MT5 server does not match expected MT5_SERVER")
        if (self.settings.demo_order_submission_enabled or self.settings.execute_tradingview_exit_alerts
                or self.settings.execution_mode == "live") and (not self.settings.mt5_login or not self.settings.mt5_server):
            raise ExecutionRejected("Expected MT5_LOGIN and MT5_SERVER are required before order submission")
        return account

    def _open_bot_positions(self) -> list[PositionSnapshot]:
        return self.broker.positions(magic=self.settings.mt5_magic)

    def _existing_risk_pct(self, equity: float) -> float:
        if equity <= 0:
            return 100.0
        total = 0.0
        for p in self._open_bot_positions():
            if not math.isfinite(p.sl) or p.sl <= 0 or not math.isfinite(p.volume) or p.volume <= 0:
                return 100.0
            risk = self.broker.risk_for_one_lot(p.side, p.symbol, p.price_open, p.sl) * p.volume
            if not math.isfinite(risk) or risk < 0:
                return 100.0
            total += risk
        return 100.0 * total / equity

    def _entry_quote(self, side: str, symbol: SymbolSnapshot) -> float:
        return symbol.ask if side == "LONG" else symbol.bid

    def _validate_stop(self, side: str, entry: float, stop: float) -> None:
        if side == "LONG" and not stop < entry:
            raise ExecutionRejected("LONG structural stop is no longer below the broker entry quote")
        if side == "SHORT" and not stop > entry:
            raise ExecutionRejected("SHORT structural stop is no longer above the broker entry quote")

    def _target_from_fill(self, side: str, fill: float, stop: float, rr: float, symbol: SymbolSnapshot) -> float:
        risk = abs(fill - stop)
        if risk <= 0:
            raise ExecutionRejected("Invalid zero/negative stop distance")
        target = fill + rr * risk if side == "LONG" else fill - rr * risk
        if not math.isfinite(target) or target <= 0:
            raise ExecutionRejected("Calculated target is not a positive finite price")
        # Round reward outward so broker tick quantization never reduces the planned 2R.
        if side == "LONG":
            return self._ceil_price(target, symbol.tick_size, symbol.digits)
        return self._floor_price(target, symbol.tick_size, symbol.digits)

    def _size(self, event: WebhookEvent, symbol: SymbolSnapshot, account_equity: float, entry: float, stop: float) -> tuple[float, float]:
        requested_risk_pct = min(float(event.risk_pct), self.settings.max_risk_pct)
        risk_cash = account_equity * requested_risk_pct / 100.0
        per_lot_loss = self.broker.risk_for_one_lot(event.side.value, symbol.name, entry, stop)
        if not math.isfinite(per_lot_loss) or per_lot_loss <= 0:
            raise ExecutionRejected("Broker returned non-positive risk per lot")
        raw_volume = risk_cash / per_lot_loss
        volume = self._floor_step(min(raw_volume, symbol.volume_max), symbol.volume_step)
        if volume + 1e-12 < symbol.volume_min:
            raise ExecutionRejected(
                f"Minimum MT5 volume {symbol.volume_min} would exceed the approved risk budget; computed {raw_volume:.8f}"
            )
        return volume, risk_cash

    def _comment(self, event: WebhookEvent) -> str:
        # ENTRY and EXIT share this identity, while chart instances and later trades
        # have different identities. A late EXIT cannot close a newer position.
        identity = json.dumps([event.instance_id, event.ticker, event.trade_id], separators=(",", ":"))
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        return f"RSI-{digest}"

    def _find_position(self, symbol: str, event: WebhookEvent) -> PositionSnapshot | None:
        positions = [p for p in self.broker.positions(symbol=symbol, magic=self.settings.mt5_magic)
                     if p.comment == self._comment(event) and p.side == event.side.value]
        if len(positions) > 1:
            raise RuntimeError("Multiple broker positions share the event trade identity; reconcile before continuing")
        return positions[0] if positions else None

    def _wait_for_position(self, symbol: str, event: WebhookEvent) -> PositionSnapshot | None:
        deadline = time.monotonic() + self.settings.reconciliation_wait_seconds
        while True:
            position = self._find_position(symbol, event)
            if position is not None:
                return position
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.10)

    def _wait_for_ticket_gone(self, symbol: str, ticket: int) -> bool:
        deadline = time.monotonic() + self.settings.reconciliation_wait_seconds
        while True:
            if all(p.ticket != ticket for p in self.broker.positions(symbol=symbol, magic=self.settings.mt5_magic)):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.10)

    def _emergency_close(self, position: PositionSnapshot, reason: str) -> None:
        result = self.broker.close_position(
            position=position,
            deviation_points=self.settings.deviation_points,
            comment="RSI-EMERGENCY",
        )
        if not result.ok and not result.uncertain:
            raise RuntimeError(f"EMERGENCY CLOSE FAILED after {reason}: {result.message}")
        if not self._wait_for_ticket_gone(position.symbol, position.ticket):
            raise RuntimeError(f"EMERGENCY CLOSE DID NOT REMOVE POSITION after {reason}; reconcile residual/partial fill")

    def process(self, event: WebhookEvent) -> dict[str, Any]:
        self.broker.connect()
        try:
            account = self._ensure_account_safe()
            symbol_name = self._map_symbol(event.ticker)
            if event.event_type == EventType.ENTRY:
                return self._process_entry(event, symbol_name, account)
            return self._process_exit(event, symbol_name)
        finally:
            self.broker.close()

    def _process_entry(self, event: WebhookEvent, symbol_name: str, account: Any) -> dict[str, Any]:
        if not self.settings.new_entries_enabled:
            raise ExecutionRejected("New entries are paused by NEW_ENTRIES_ENABLED=false")

        age = time.time() - (event.signal_time_ms / 1000.0)
        if age < -self.settings.max_future_skew_seconds:
            raise ExecutionRejected("Entry timestamp is in the future")
        if age > self.settings.max_event_age_seconds:
            raise ExecutionRejected(f"Stale entry event ({age:.1f}s old)")

        open_positions = self._open_bot_positions()
        if len(open_positions) >= self.settings.max_open_positions:
            raise ExecutionRejected("Account-wide bot position limit reached")
        if any(p.symbol == symbol_name for p in self.broker.positions(symbol=symbol_name)):
            raise ExecutionRejected("An MT5 position already exists on this symbol; refusing accidental netting/reversal")

        existing_risk_pct = self._existing_risk_pct(account.equity)
        if existing_risk_pct >= self.settings.max_total_risk_pct:
            raise ExecutionRejected("Account-wide bot risk cap already reached")

        symbol = self.broker.symbol(symbol_name)
        metadata = [symbol.bid, symbol.ask, symbol.point, symbol.tick_size, symbol.volume_min,
                    symbol.volume_max, symbol.volume_step]
        if not all(math.isfinite(value) and value > 0 for value in metadata) or symbol.ask < symbol.bid:
            raise ExecutionRejected("Invalid broker quote or contract metadata")
        if symbol.volume_max < symbol.volume_min:
            raise ExecutionRejected("Invalid broker volume bounds")
        quote_age = time.time() - symbol.quote_time_ms / 1000.0
        if symbol.quote_time_ms <= 0 or quote_age > self.settings.max_quote_age_seconds or quote_age < -self.settings.max_future_skew_seconds:
            raise ExecutionRejected("Broker quote is stale or has an invalid timestamp")
        spread_points = (symbol.ask - symbol.bid) / symbol.point if symbol.point > 0 else math.inf
        if spread_points > self.settings.max_spread_points:
            raise ExecutionRejected(f"Spread {spread_points:.1f} points exceeds cap")

        entry_quote = self._entry_quote(event.side.value, symbol)
        broker_stop = self._normalize_stop(event.side.value, event.structural_stop, symbol)
        self._validate_stop(event.side.value, entry_quote, broker_stop)
        volume, risk_cash = self._size(event, symbol, account.equity, entry_quote, broker_stop)

        per_lot_loss = self.broker.risk_for_one_lot(event.side.value, symbol.name, entry_quote, broker_stop)
        new_risk_pct = (per_lot_loss * volume) / account.equity * 100.0 if account.equity > 0 else 100.0
        if existing_risk_pct + new_risk_pct > self.settings.max_total_risk_pct + 1e-9:
            raise ExecutionRejected("New entry would exceed account-wide total risk cap")

        margin = self.broker.required_margin(event.side.value, symbol.name, volume, entry_quote)
        if not math.isfinite(margin) or margin < 0 or margin > account.margin_free * self.settings.max_margin_fraction:
            raise ExecutionRejected("Required margin exceeds configured free-margin fraction")

        provisional_tp = self._target_from_fill(event.side.value, entry_quote, broker_stop, event.rr, symbol)
        if not self.settings.demo_order_submission_enabled and self.settings.execution_mode == "demo":
            return {
                "status": "DRY_RUN_DEMO",
                "symbol": symbol.name,
                "side": event.side.value,
                "volume": volume,
                "entry_quote": entry_quote,
                "sl": broker_stop,
                "tp": provisional_tp,
                "risk_cash_budget": risk_cash,
                "risk_pct_after_rounding": new_risk_pct,
            }

        result = self.broker.open_market(
            side=event.side.value,
            symbol=symbol.name,
            volume=volume,
            sl=broker_stop,
            tp=provisional_tp,
            magic=self.settings.mt5_magic,
            deviation_points=self.settings.deviation_points,
            comment=self._comment(event),
        )

        # Reconcile every successful or uncertain submission before taking any further
        # action. An uncertain transport/server result must never be blindly retried.
        position = self._wait_for_position(symbol.name, event) if (result.ok or result.uncertain) else None
        if not result.ok and not result.uncertain:
            raise ExecutionRejected(f"MT5 entry rejected: retcode={result.retcode} {result.message}")
        if position is None:
            if result.uncertain:
                raise RuntimeError(
                    f"MT5 entry outcome is uncertain (retcode={result.retcode} {result.message}); "
                    "no matching position was found during the reconciliation window. Manual reconciliation is required before retry."
                )
            raise RuntimeError("MT5 reported a completed entry but no matching bot position was found during reconciliation")

        # Do not widen the structural stop after a gap. If the fill has already crossed
        # invalidation, get out instead of manufacturing a new stop.
        try:
            self._validate_stop(event.side.value, position.price_open, broker_stop)
        except ExecutionRejected as exc:
            self._emergency_close(position, str(exc))
            raise

        actual_risk = self.broker.risk_for_one_lot(event.side.value, symbol.name, position.price_open, broker_stop) * position.volume
        overrun = ((actual_risk - risk_cash) / risk_cash * 100.0) if risk_cash > 0 else 100.0
        exceeds_caps = (actual_risk > account.equity * self.settings.max_risk_pct / 100.0 + 1e-8 or
                        existing_risk_pct + actual_risk / account.equity * 100 > self.settings.max_total_risk_pct + 1e-9)
        if not math.isfinite(actual_risk) or overrun > self.settings.max_risk_overrun_pct or exceeds_caps:
            self._emergency_close(position, f"risk overrun {overrun:.2f}%")
            raise ExecutionRejected(f"Actual fill risk exceeded budget by {overrun:.2f}%; position emergency-closed")

        final_tp = self._target_from_fill(event.side.value, position.price_open, broker_stop, event.rr, symbol)
        try:
            protection = self.broker.set_protection(
                position_ticket=position.ticket, symbol=symbol.name, sl=broker_stop, tp=final_tp)
        except Exception as exc:
            self._emergency_close(position, "protection update exception")
            raise RuntimeError("Protection update was uncertain; position emergency-closed") from exc
        if not protection.ok:
            self._emergency_close(position, "protection update failure")
            raise RuntimeError(f"Protection update failed and position was emergency-closed: {protection.message}")

        confirmed = self._find_position(symbol.name, event)
        tolerance = max(symbol.tick_size * 1e-6, 1e-12)
        if (confirmed is None or abs(confirmed.sl - broker_stop) > tolerance
                or abs(confirmed.tp - final_tp) > tolerance):
            if confirmed is not None:
                self._emergency_close(confirmed, "incorrect broker-side SL/TP after update")
            raise RuntimeError("Broker-side protection could not be confirmed")

        return {
            "status": "DEMO_ORDER_OPENED" if self.settings.execution_mode == "demo" else "LIVE_ORDER_OPENED",
            "symbol": symbol.name,
            "side": event.side.value,
            "position_ticket": confirmed.ticket,
            "volume": confirmed.volume,
            "fill": confirmed.price_open,
            "sl": confirmed.sl,
            "tp": confirmed.tp,
            "actual_risk_cash": actual_risk,
        }

    def _process_exit(self, event: WebhookEvent, symbol_name: str) -> dict[str, Any]:
        positions = self.broker.positions(symbol=symbol_name, magic=self.settings.mt5_magic)
        if not positions:
            # Broker-side SL/TP may already have closed it. Never open an opposite position.
            return {"status": "NO_POSITION_NOOP", "symbol": symbol_name}

        # The current strategy has no discretionary early-exit rule: its exits are the
        # protective stop and 2R target. Those are submitted broker-side on entry and
        # the broker is authoritative. TradingView's simulated fill can differ slightly
        # because its feed/fill is not the MT5 fill, so do not close a valid MT5 position
        # from a simulated TV bracket event unless this advanced switch is explicitly set.
        if not self.settings.execute_tradingview_exit_alerts:
            return {
                "status": "TV_EXIT_OBSERVED_BROKER_PROTECTION_AUTHORITATIVE",
                "symbol": symbol_name,
                "tickets": [p.ticket for p in positions],
            }

        positions = [p for p in positions if p.comment == self._comment(event) and p.side == event.side.value]
        if not positions:
            return {"status": "NO_MATCHING_TRADE_NOOP", "symbol": symbol_name}
        if len(positions) != 1:
            raise RuntimeError("EXIT identity matched multiple broker positions; reconcile before closing")

        results = []
        for position in positions:
            close_result = self.broker.close_position(
                position=position,
                deviation_points=self.settings.deviation_points,
                comment=self._comment(event),
            )
            if close_result.uncertain:
                if not self._wait_for_ticket_gone(symbol_name, position.ticket):
                    raise RuntimeError(
                        f"MT5 close outcome is uncertain for position {position.ticket}; "
                        "manual reconciliation is required before retry"
                    )
            elif not close_result.ok:
                raise RuntimeError(f"Failed to close position {position.ticket}: {close_result.message}")
            elif not self._wait_for_ticket_gone(symbol_name, position.ticket):
                raise RuntimeError(f"MT5 reported close success but position {position.ticket} is still open")
            results.append(position.ticket)
        return {"status": "POSITIONS_CLOSED", "symbol": symbol_name, "tickets": results}
