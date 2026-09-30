from __future__ import annotations

import argparse
import logging
import threading
from contextlib import nullcontext

import uvicorn

from .http_app import create_app
from .config import Settings
from .db import EventStore
from .worker import run_worker
from .lease import WorkerLease


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-worker", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    settings.validate()
    store = EventStore(settings.database_path)

    stop_event = threading.Event()
    thread = None
    with WorkerLease(settings.database_path) if not args.no_worker else nullcontext():
        if not args.no_worker:
            thread = threading.Thread(target=run_worker, args=(settings, store, 0.25, stop_event),
                                      daemon=True, name="execution-worker")
            thread.start()
        try:
            # Webhook tokens occur in URL paths: disable the default access log so a
            # successful authenticated webhook cannot publish its token to logs.
            uvicorn.run(create_app(settings, store), host=args.host, port=args.port,
                        log_level="info", access_log=False)
        finally:
            stop_event.set()
            if thread is not None:
                thread.join(timeout=10)
                if thread.is_alive():
                    # Do not release the worker lease while a broker call is outstanding.
                    # Terminating the process leaves PROCESSING for recovery on restart.
                    thread.join()


if __name__ == "__main__":
    main()
