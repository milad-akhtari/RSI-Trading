from __future__ import annotations

import logging
import threading

from .config import Settings
from .db import EventStore
from .engine import ExecutionEngine, ExecutionRejected
from .models import EventType, WebhookEvent
from .mt5_client import MT5Broker

log = logging.getLogger(__name__)


def process_next(store: EventStore, engine: ExecutionEngine) -> bool:
    item = store.claim_next()
    if item is None:
        return False
    event = WebhookEvent.model_validate(item.payload)
    if event.event_type == EventType.ENTRY and store.entry_pause_reason():
        store.fail(event.event_id, "New entries paused pending broker reconciliation", retry=False)
        return True
    try:
        result = engine.process(event)
        store.complete(event.event_id, result)
        log.info("event %s done: %s", event.event_id, result.get("status"))
    except ExecutionRejected as exc:
        store.fail(event.event_id, str(exc), retry=False)
        log.warning("event %s rejected: %s", event.event_id, exc)
    except Exception as exc:
        # The request may have reached MT5. Quarantine it and pause ALL later entries,
        # including other chart instances; broker-side protection remains active.
        store.require_reconciliation(event.event_id, str(exc))
        log.error("event %s requires broker reconciliation: %s", event.event_id, type(exc).__name__)
    return True


def run_worker(settings: Settings, store: EventStore, poll_seconds: float = 0.25,
               stop_event: threading.Event | None = None) -> None:
    broker = MT5Broker(settings)
    engine = ExecutionEngine(settings, broker)
    quarantined = store.mark_processing_for_reconciliation()
    if quarantined:
        log.error("%s interrupted event(s) require broker reconciliation before any retry", quarantined)
    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        if not process_next(store, engine):
            stop_event.wait(poll_seconds)
