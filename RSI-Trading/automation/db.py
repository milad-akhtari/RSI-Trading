from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import WebhookEvent


@dataclass
class StoredEvent:
    event_id: str
    status: str
    attempts: int
    payload: dict[str, Any]
    last_error: str | None


class EventConflict(ValueError):
    """An event ID or logical trade was reused with different contents."""


class EventStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # Stay below TradingView's three-second acknowledgement deadline under contention.
        conn = sqlite3.connect(self.path, timeout=0.5, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            # SQLite's transaction context does not close the connection itself.
            # Preserve commit/rollback behavior, then release Windows file handles.
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    result_json TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_status ON events(status, received_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_logical_trade ON events(
                    json_extract(payload_json, '$.instance_id'),
                    json_extract(payload_json, '$.ticker'),
                    json_extract(payload_json, '$.trade_id'),
                    json_extract(payload_json, '$.event_type')
                );
                CREATE TABLE IF NOT EXISTS safety_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    reason TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def accept(self, event: WebhookEvent) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        payload = event.model_dump_json()
        try:
            with self._lock, self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO events(event_id, received_at, payload_json, status, updated_at) VALUES (?, ?, ?, 'PENDING', ?)",
                    (event.event_id, now, payload, now),
                )
                conn.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            row = self.get(event.event_id)
            if row is not None and json.loads(row["payload_json"]) == json.loads(payload):
                return False
            raise EventConflict("Event identity was reused with different payload or logical trade ID")

    def claim_next(self) -> StoredEvent | None:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT event_id, status, attempts, payload_json, last_error FROM events WHERE status='PENDING' ORDER BY received_at LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                "UPDATE events SET status='PROCESSING', attempts=attempts+1, updated_at=? WHERE event_id=?",
                (datetime.now(timezone.utc).isoformat(), row["event_id"]),
            )
            conn.execute("COMMIT")
            return StoredEvent(
                event_id=row["event_id"],
                status="PROCESSING",
                attempts=row["attempts"] + 1,
                payload=json.loads(row["payload_json"]),
                last_error=row["last_error"],
            )


    def mark_processing_for_reconciliation(self) -> int:
        """Quarantine events that were being processed when the worker stopped.

        We deliberately do not place them back in PENDING: an MT5 request may have
        reached the broker before the process died, so blind retry could duplicate a
        position. They require broker reconciliation first.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "UPDATE events SET status='RECONCILIATION_REQUIRED', "
                "last_error='Worker restarted while event was PROCESSING; reconcile broker state before retry', "
                "updated_at=? WHERE status='PROCESSING'",
                (now,),
            )
            count = int(cur.rowcount)
            if count:
                conn.execute("INSERT INTO safety_state(id, reason, updated_at) VALUES (1, ?, ?) "
                             "ON CONFLICT(id) DO UPDATE SET reason=excluded.reason, updated_at=excluded.updated_at",
                             ("Interrupted broker event requires account reconciliation", now))
            conn.execute("COMMIT")
        return count

    def pause_entries(self, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO safety_state(id, reason, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET reason=excluded.reason, updated_at=excluded.updated_at",
                (reason[:2000], datetime.now(timezone.utc).isoformat()),
            )

    def entry_pause_reason(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT reason FROM safety_state WHERE id=1").fetchone()
            return str(row["reason"]) if row and row["reason"] else None

    def resume_entries(self) -> None:
        # Only the local operator recovery command calls this after broker reconciliation.
        with self._connect() as conn:
            conn.execute("UPDATE safety_state SET reason=NULL, updated_at=? WHERE id=1",
                         (datetime.now(timezone.utc).isoformat(),))

    def require_reconciliation(self, event_id: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        # Persist event quarantine and the entry pause in the same transaction.
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE events SET status='RECONCILIATION_REQUIRED', last_error=?, updated_at=? WHERE event_id=?",
                         (error[:2000], now, event_id))
            conn.execute("INSERT INTO safety_state(id, reason, updated_at) VALUES (1, ?, ?) "
                         "ON CONFLICT(id) DO UPDATE SET reason=excluded.reason, updated_at=excluded.updated_at",
                         (f"Reconcile event {event_id} before resuming entries", now))
            conn.execute("COMMIT")

    def complete(self, event_id: str, result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE events SET status='DONE', result_json=?, last_error=NULL, updated_at=? WHERE event_id=?",
                (json.dumps(result, sort_keys=True), now, event_id),
            )

    def fail(self, event_id: str, error: str, retry: bool = False) -> None:
        now = datetime.now(timezone.utc).isoformat()
        status = "PENDING" if retry else "FAILED"
        with self._connect() as conn:
            conn.execute(
                "UPDATE events SET status=?, last_error=?, updated_at=? WHERE event_id=?",
                (status, error[:2000], now, event_id),
            )

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            return dict(row) if row else None
