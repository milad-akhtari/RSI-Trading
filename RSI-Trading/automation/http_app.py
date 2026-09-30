from __future__ import annotations

import hmac
import json
import sqlite3

from fastapi import FastAPI, HTTPException, status

from .config import Settings
from .db import EventConflict, EventStore
from .models import WebhookEvent


def create_app(settings: Settings | None = None, store: EventStore | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.validate()
    store = store or EventStore(settings.database_path)

    app = FastAPI(title="RSI Trend Strategy Execution Gateway", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "execution_mode": settings.execution_mode,
            "demo_order_submission_enabled": settings.demo_order_submission_enabled,
            "live_trading_enabled": settings.live_trading_enabled,
            "new_entries_enabled": settings.new_entries_enabled,
            "entries_paused_for_reconciliation": store.entry_pause_reason() is not None,
        }

    @app.post("/tradingview/{token}", status_code=status.HTTP_202_ACCEPTED)
    def tradingview_webhook(token: str, event: WebhookEvent) -> dict[str, object]:
        if not hmac.compare_digest(token, settings.webhook_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook token")
        try:
            inserted = store.accept(event)
        except EventConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except sqlite3.OperationalError as exc:
            # A failed durable write is never reported as an accepted webhook.
            raise HTTPException(status_code=503, detail="event store temporarily unavailable") from exc
        return {"accepted": True, "duplicate": not inserted, "event_id": event.event_id}

    @app.get("/status/{token}/{event_id}")
    def event_status(token: str, event_id: str) -> dict[str, object]:
        if not hmac.compare_digest(token, settings.webhook_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook token")
        row = store.get(event_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
        result = json.loads(row["result_json"]) if row.get("result_json") else None
        return {
            "event_id": event_id,
            "status": row["status"],
            "attempts": row["attempts"],
            "last_error": row["last_error"],
            "result": result,
        }

    return app


