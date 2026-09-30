from __future__ import annotations

import math
from typing import Any

from .broker import AccountSnapshot, Broker, OrderResult, PositionSnapshot, SymbolSnapshot
from .config import Settings


class MT5Unavailable(RuntimeError):
    pass


class MT5Broker(Broker):
    """Thin adapter around MetaQuotes' official MetaTrader5 Python package.

    The package communicates with a locally installed MetaTrader 5 terminal. This
    adapter intentionally imports it lazily so Linux CI can run all non-MT5 tests.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.mt5: Any | None = None

    def _module(self):
        if self.mt5 is not None:
            return self.mt5
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception as exc:  # pragma: no cover - platform specific
            raise MT5Unavailable(
                "MetaTrader5 Python package is unavailable. Run the execution service on Windows with the MT5 desktop terminal installed."
            ) from exc
        self.mt5 = mt5
        return mt5

    def connect(self) -> None:
        mt5 = self._module()
        kwargs: dict[str, Any] = {}
        if self.settings.mt5_login is not None:
            kwargs["login"] = self.settings.mt5_login
        if self.settings.mt5_password:
            kwargs["password"] = self.settings.mt5_password
        if self.settings.mt5_server:
            kwargs["server"] = self.settings.mt5_server

        if self.settings.mt5_terminal_path:
            ok = mt5.initialize(self.settings.mt5_terminal_path, **kwargs)
        else:
            ok = mt5.initialize(**kwargs)
        if not ok:
            raise RuntimeError(f"mt5.initialize failed: {mt5.last_error()}")

    def close(self) -> None:
        if self.mt5 is not None:
            self.mt5.shutdown()

    def account(self) -> AccountSnapshot:
        mt5 = self._module()
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info failed: {mt5.last_error()}")
        return AccountSnapshot(
            is_demo=int(info.trade_mode) == 0,
            equity=float(info.equity),
            margin_free=float(info.margin_free),
            currency=str(info.currency),
            trade_allowed=bool(info.trade_allowed),
            trade_expert=bool(info.trade_expert),
            login=int(info.login),
            server=str(info.server),
        )

    def symbol(self, name: str) -> SymbolSnapshot:
        self.settings.validate_quote_clock()
        mt5 = self._module()
        offset = self.settings.mt5_quote_time_offset_seconds
        if offset:
            account = mt5.account_info()
            if account is None or str(account.server) != self.settings.mt5_quote_time_offset_server:
                raise RuntimeError("Quote clock offset refused: connected MT5 server does not match the configured offset server")
        info = mt5.symbol_info(name)
        if info is None:
            raise RuntimeError(f"symbol_info({name}) failed: {mt5.last_error()}")
        if not bool(info.visible):
            if not mt5.symbol_select(name, True):
                raise RuntimeError(f"symbol_select({name}) failed: {mt5.last_error()}")
            info = mt5.symbol_info(name)
        tick = mt5.symbol_info_tick(name)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick({name}) failed: {mt5.last_error()}")
        raw_time_ms = int(getattr(tick, "time_msc", 0) or int(tick.time) * 1000)
        # Preserve missing/invalid timestamps so an offset cannot turn them fresh.
        quote_time_ms = raw_time_ms - offset * 1000 if raw_time_ms > 0 else raw_time_ms
        return SymbolSnapshot(
            name=name,
            point=float(info.point),
            tick_size=float(getattr(info, "trade_tick_size", 0.0) or info.point),
            digits=int(info.digits),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
            volume_step=float(info.volume_step),
            bid=float(tick.bid),
            ask=float(tick.ask),
            quote_time_ms=quote_time_ms,
        )

    def positions(self, symbol: str | None = None, magic: int | None = None) -> list[PositionSnapshot]:
        mt5 = self._module()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            raise RuntimeError(f"positions_get failed: {mt5.last_error()}")
        out: list[PositionSnapshot] = []
        for p in raw:
            if magic is not None and int(getattr(p, "magic", 0)) != magic:
                continue
            side = "LONG" if int(p.type) == int(mt5.POSITION_TYPE_BUY) else "SHORT"
            out.append(
                PositionSnapshot(
                    ticket=int(p.ticket),
                    symbol=str(p.symbol),
                    side=side,
                    volume=float(p.volume),
                    price_open=float(p.price_open),
                    sl=float(p.sl),
                    tp=float(p.tp),
                    magic=int(getattr(p, "magic", 0)),
                    comment=str(getattr(p, "comment", "")),
                )
            )
        return out

    def risk_for_one_lot(self, side: str, symbol: str, entry: float, stop: float) -> float:
        mt5 = self._module()
        order_type = mt5.ORDER_TYPE_BUY if side == "LONG" else mt5.ORDER_TYPE_SELL
        pnl = mt5.order_calc_profit(order_type, symbol, 1.0, entry, stop)
        if pnl is None:
            raise RuntimeError(f"order_calc_profit failed: {mt5.last_error()}")
        return abs(float(pnl))

    def required_margin(self, side: str, symbol: str, volume: float, entry: float) -> float:
        mt5 = self._module()
        order_type = mt5.ORDER_TYPE_BUY if side == "LONG" else mt5.ORDER_TYPE_SELL
        margin = mt5.order_calc_margin(order_type, symbol, volume, entry)
        if margin is None:
            raise RuntimeError(f"order_calc_margin failed: {mt5.last_error()}")
        return float(margin)

    def _send_with_filling_fallback(self, request: dict[str, Any]) -> OrderResult:
        mt5 = self._module()
        # RETURN can leave an unfilled remainder working after a partial fill. Market
        # entries and closes use FOK/IOC only, so an accepted partial fill has no hidden
        # remaining order that could increase exposure after reconciliation.
        candidates = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC]
        last_message = ""
        last_retcode: int | None = None
        for filling in candidates:
            req = dict(request)
            req["type_filling"] = filling
            check = mt5.order_check(req)
            if check is None:
                last_message = f"order_check returned None: {mt5.last_error()}"
                continue
            last_retcode = int(check.retcode)
            # 0 means a successful check in the Python integration examples.
            if int(check.retcode) != 0:
                last_message = f"order_check retcode={check.retcode} comment={getattr(check, 'comment', '')}"
                continue
            result = mt5.order_send(req)
            if result is None:
                # Unknown transport outcome: never try another fill mode blindly, because
                # the first request may have reached the broker. Reconcile positions first.
                return OrderResult(
                    ok=False,
                    message=f"order_send returned None: {mt5.last_error()}",
                    uncertain=True,
                )

            retcode = int(result.retcode)
            ok_codes = {int(mt5.TRADE_RETCODE_DONE)}
            if hasattr(mt5, "TRADE_RETCODE_DONE_PARTIAL"):
                ok_codes.add(int(mt5.TRADE_RETCODE_DONE_PARTIAL))
            if retcode in ok_codes:
                return OrderResult(
                    ok=True,
                    order_ticket=int(result.order) if getattr(result, "order", 0) else None,
                    deal_ticket=int(result.deal) if getattr(result, "deal", 0) else None,
                    retcode=retcode,
                    message=str(getattr(result, "comment", "")),
                )

            invalid_fill = int(getattr(mt5, "TRADE_RETCODE_INVALID_FILL", 10030))
            if retcode == invalid_fill:
                last_retcode = retcode
                last_message = str(getattr(result, "comment", "invalid filling mode"))
                continue

            uncertain_codes = {
                int(getattr(mt5, "TRADE_RETCODE_TIMEOUT", 10012)),
                int(getattr(mt5, "TRADE_RETCODE_CONNECTION", 10031)),
                int(getattr(mt5, "TRADE_RETCODE_LOCKED", 10028)),
                int(getattr(mt5, "TRADE_RETCODE_PLACED", 10008)),
            }
            return OrderResult(
                ok=False,
                order_ticket=int(result.order) if getattr(result, "order", 0) else None,
                deal_ticket=int(result.deal) if getattr(result, "deal", 0) else None,
                retcode=retcode,
                message=str(getattr(result, "comment", "")),
                uncertain=retcode in uncertain_codes,
            )
        return OrderResult(ok=False, retcode=last_retcode, message=last_message or "No supported filling mode accepted")

    def open_market(self, *, side: str, symbol: str, volume: float, sl: float, tp: float, magic: int, deviation_points: int, comment: str) -> OrderResult:
        mt5 = self._module()
        snap = self.symbol(symbol)
        order_type = mt5.ORDER_TYPE_BUY if side == "LONG" else mt5.ORDER_TYPE_SELL
        price = snap.ask if side == "LONG" else snap.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": int(deviation_points),
            "magic": int(magic),
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
        }
        return self._send_with_filling_fallback(request)

    def set_protection(self, *, position_ticket: int, symbol: str, sl: float, tp: float) -> OrderResult:
        mt5 = self._module()
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(position_ticket),
            "symbol": symbol,
            "sl": float(sl),
            "tp": float(tp),
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(ok=False, message=f"order_send(SLTP) failed: {mt5.last_error()}")
        ok = int(result.retcode) in {
            int(mt5.TRADE_RETCODE_DONE), int(getattr(mt5, "TRADE_RETCODE_NO_CHANGES", 10025))
        }
        return OrderResult(ok=ok, order_ticket=int(result.order) if getattr(result, "order", 0) else None, retcode=int(result.retcode), message=str(getattr(result, "comment", "")))

    def close_position(self, *, position: PositionSnapshot, deviation_points: int, comment: str) -> OrderResult:
        mt5 = self._module()
        snap = self.symbol(position.symbol)
        if position.side == "LONG":
            order_type = mt5.ORDER_TYPE_SELL
            price = snap.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = snap.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(position.ticket),
            "symbol": position.symbol,
            "volume": float(position.volume),
            "type": order_type,
            "price": price,
            "deviation": int(deviation_points),
            "magic": int(position.magic),
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
        }
        return self._send_with_filling_fallback(request)
