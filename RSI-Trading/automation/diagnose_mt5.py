from __future__ import annotations

import json

from .config import Settings
from .mt5_client import MT5Broker


def main() -> None:
    """Read-only MT5 connectivity/symbol diagnostic. It never submits an order."""
    settings = Settings()
    settings.validate()
    broker = MT5Broker(settings)
    broker.connect()
    try:
        account = broker.account()
        print(json.dumps({
            "account": {
                "is_demo": account.is_demo,
                "equity": account.equity,
                "margin_free": account.margin_free,
                "currency": account.currency,
                "trade_allowed": account.trade_allowed,
                "trade_expert": account.trade_expert,
            },
            "execution_mode": settings.execution_mode,
            "demo_order_submission_enabled": settings.demo_order_submission_enabled,
            "live_trading_enabled": settings.live_trading_enabled,
            "new_entries_enabled": settings.new_entries_enabled,
        }, indent=2))

        for symbol_name in settings.allowed_symbols:
            try:
                symbol = broker.symbol(symbol_name)
                print(json.dumps({
                    "symbol": symbol.name,
                    "bid": symbol.bid,
                    "ask": symbol.ask,
                    "point": symbol.point,
                    "tick_size": symbol.tick_size,
                    "digits": symbol.digits,
                    "volume_min": symbol.volume_min,
                    "volume_max": symbol.volume_max,
                    "volume_step": symbol.volume_step,
                }, indent=2))
            except Exception as exc:
                print(json.dumps({"symbol": symbol_name, "error": str(exc)}, indent=2))
    finally:
        broker.close()


if __name__ == "__main__":
    main()
