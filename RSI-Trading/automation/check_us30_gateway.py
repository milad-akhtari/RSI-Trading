"""Isolated loopback HTTP/SQLite/worker check with native MT5 reads and no orders."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import uvicorn

from .http_app import create_app
from .broker import Broker
from .config import Settings
from .db import EventStore
from .dry_run_mt5 import ReadOnlyBroker, readonly_settings, synthetic_event
from .engine import ExecutionEngine, ExecutionRejected
from .mt5_client import MT5Broker
from .worker import process_next


@contextmanager
def loopback_server(app):
    """Bind only IPv4 loopback, choose a free port and suppress token-bearing logs."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=0, loop="asyncio", access_log=False,
            log_config=None, log_level="critical",
        ))
        errors = []
        def serve():
            try:
                server.run(sockets=[listener])
            except BaseException:
                # Do not print exception URLs, requests or authentication tokens.
                errors.append("Isolated loopback server failed to start")
        thread = threading.Thread(target=serve, daemon=True, name="readonly-http-check")
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.02)
            if not server.started or errors:
                raise RuntimeError("Isolated loopback server did not start within five seconds")
            yield "http://127.0.0.1:" + str(listener.getsockname()[1])
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                server.force_exit = True
                thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Isolated loopback server did not stop")


def http_json(root: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    request = Request(root + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    # Loopback traffic must not be sent through a machine's configured HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    try:
        response = opener.open(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.code, json.loads(response.read())


def run_check(settings: Settings, broker: Broker, *, stop_distance: float = 100,
              risk_pct: float = 1) -> dict:
    # Validate/refuse armed configurations before binding or connecting to MT5.
    safe = readonly_settings(settings, "US30", risk_pct, "CAPITALCOM:US30")
    readonly = ReadOnlyBroker(broker)
    results = []
    with tempfile.TemporaryDirectory(prefix="rsi-readonly-gateway-") as directory:
        db_path = Path(directory) / "test-events.sqlite3"
        safe = replace(safe, database_path=db_path, webhook_token=secrets.token_urlsafe(32))
        store = EventStore(db_path)
        engine = ExecutionEngine(safe, readonly)
        with loopback_server(create_app(safe, store)) as root:
            for side in ("LONG", "SHORT"):
                readonly.connect()
                try:
                    engine._ensure_account_safe()
                    event = synthetic_event(readonly.symbol("US30"), side, stop_distance, risk_pct)
                    payload = event.model_dump(mode="json")
                    payload["ticker"] = "CAPITALCOM:US30"
                finally:
                    readonly.close()
                post_path = "/tradingview/" + safe.webhook_token
                status_path = "/status/" + safe.webhook_token + "/" + event.event_id
                first_code, first = http_json(root, post_path, payload)
                duplicate_code, duplicate = http_json(root, post_path, payload)
                conflict_code, _ = http_json(root, post_path, {**payload, "strength": "CONFLICT_TEST"})
                if not (first_code == duplicate_code == 202 and first.get("accepted")
                        and not first.get("duplicate") and duplicate.get("duplicate")
                        and conflict_code == 409):
                    raise RuntimeError("HTTP receipt, deduplication or conflict check failed")
                _, pending = http_json(root, status_path)
                if pending.get("status") != "PENDING" or pending.get("attempts") != 0:
                    raise RuntimeError("Expected one durably queued event before worker processing")
                if not process_next(store, engine):
                    raise RuntimeError("Worker did not claim the queued test event")
                _, done = http_json(root, status_path)
                if done.get("status") == "FAILED":
                    raise ExecutionRejected(done.get("last_error") or "Native check rejected")
                calculation = done.get("result") or {}
                if not (done.get("status") == "DONE" and done.get("attempts") == 1
                        and calculation.get("status") == "DRY_RUN_DEMO"):
                    raise RuntimeError("Isolated worker check did not complete a single read-only dry run")
                # Re-open the temporary DB independently; completed events must not retry.
                reopened = EventStore(db_path)
                saved = reopened.get(event.event_id)
                if not (saved and saved["status"] == "DONE" and saved["attempts"] == 1
                        and json.loads(saved["result_json"]) == calculation
                        and not process_next(reopened, engine)):
                    raise RuntimeError("Saved result or completed-event no-retry check failed")
                results.append({
                    "side": side, "http_receipt": first_code,
                    "duplicate_detected": True, "conflicting_payload_rejected": True,
                    "durable_status": "DONE", "attempts": 1,
                    "saved_result_verified": True, "completed_event_not_retried": True,
                    "margin_required": readonly.last_margin, "result": calculation,
                })
    return {
        "status": "GATEWAY_CHECK_PASSED", "synthetic_test_only": True,
        "broker_writes_blocked": True, "settings_file_changed": False,
        "gateway_database_changed": False, "isolated_temporary_database": True,
        "quote_clock": {"offset_seconds": settings.mt5_quote_time_offset_seconds,
                        "offset_server": settings.mt5_quote_time_offset_server},
        "scope": "Loopback HTTP, temporary SQLite and worker.process_next with native sizing reads; no TradingView signal/delivery, daemon lease, process restart, order, fill or protection execution verified",
        "checks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop-distance", type=float, default=100,
                        help="Synthetic distance in US30 index price points (default 100)")
    parser.add_argument("--risk-pct", type=float, default=1)
    parser.add_argument("--quote-time-offset-seconds", type=int, default=None)
    parser.add_argument("--quote-time-offset-server", default=None)
    args = parser.parse_args()
    try:
        settings = Settings()
        overrides = {}
        if args.quote_time_offset_seconds is not None:
            overrides["mt5_quote_time_offset_seconds"] = args.quote_time_offset_seconds
        if args.quote_time_offset_server is not None:
            overrides["mt5_quote_time_offset_server"] = args.quote_time_offset_server
        settings = replace(settings, **overrides)
        output = run_check(settings, MT5Broker(settings), stop_distance=args.stop_distance,
                           risk_pct=args.risk_pct)
    except ExecutionRejected as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error), "broker_writes_blocked": True}, indent=2))
        return 2
    except Exception as error:
        # Network errors can contain a token-bearing URL; do not echo their details.
        reason = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
        print(json.dumps({"status": "CHECK_FAILED", "reason": reason, "broker_writes_blocked": True}, indent=2))
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
