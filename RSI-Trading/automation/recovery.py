"""Local operator recovery; reads MT5 state and never submits an order."""
from __future__ import annotations

import argparse
import json
import math

from .config import Settings
from .db import EventStore
from .engine import ExecutionEngine
from .lease import WorkerLease
from .mt5_client import MT5Broker


def resume_after_review(settings: Settings, store: EventStore, broker) -> None:
    # Stop the service first. Hold the same lease so resuming cannot race a worker.
    with WorkerLease(settings.database_path):
        broker.connect()
        try:
            ExecutionEngine(settings, broker)._ensure_account_safe()
            if not settings.mt5_login or not settings.mt5_server:
                raise RuntimeError("Pin the expected MT5_LOGIN and MT5_SERVER before recovery")
            for position in broker.positions(magic=settings.mt5_magic):
                if not all(math.isfinite(x) and x > 0 for x in [position.sl, position.tp]):
                    raise RuntimeError("Bot position is missing protection; reconcile it in MT5 first")
            store.resume_entries()
        finally:
            broker.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--broker-reviewed", action="store_true",
                        help="Confirm you reviewed terminal positions, pending orders and deal history for uncertain events")
    args = parser.parse_args()
    settings = Settings()
    settings.validate()
    store = EventStore(settings.database_path)
    if args.resume:
        if not args.broker_reviewed:
            parser.error("--resume requires --broker-reviewed after manual MT5 reconciliation")
        resume_after_review(settings, store, MT5Broker(settings))
    print(json.dumps({"entries_paused": store.entry_pause_reason() is not None,
                      "reason": store.entry_pause_reason(),
                      "events_requeued": False}))


if __name__ == "__main__":
    main()
