"""Desktop entry point: reuse a chosen local .env, run isolated reads, never orders."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path


def check_installation(settings_directory: Path, broker_factory=None) -> dict:
    # Load this explicit installation before importing automation/config.py.
    # Existing process environment wins; an armed setting is refused, not hidden.
    env_file = settings_directory.resolve() / ".env"
    if not env_file.is_file():
        raise ValueError("Existing project .env was not found; no settings were created")
    from dotenv import load_dotenv
    load_dotenv(env_file, override=False)
    from automation.config import Settings
    from automation.dry_run_mt5 import readonly_settings
    from automation.check_us30_gateway import run_check
    from automation.mt5_client import MT5Broker

    # This is the previously measured, explicitly server-bound read-only preset.
    # The native adapter refuses a different server or stale/future quotes.
    settings = replace(Settings(), mt5_quote_time_offset_seconds=10800,
                       mt5_quote_time_offset_server="MetaQuotes-Demo")
    readonly_settings(settings, "US30", 1, "CAPITALCOM:US30")
    broker = (broker_factory or MT5Broker)(settings)
    return run_check(settings, broker, stop_distance=90, risk_pct=1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = check_installation(args.settings_directory)
        code = 0
    except Exception as error:
        # Avoid echoing native/API errors that might contain URLs or credentials.
        reason = str(error) if isinstance(error, ValueError) or type(error).__name__ == "ExecutionRejected" else type(error).__name__
        result = {"status": "READONLY_CHECK_FAILED", "reason": reason,
                  "broker_writes_blocked": True, "settings_file_changed": False}
        code = 2
    output = json.dumps(result, indent=2, allow_nan=False)
    print(output)
    report = Path(__file__).resolve().with_name("US30_READONLY_RESULT.json")
    try:
        report.write_text(output + "\n", encoding="utf-8")
    except OSError:
        print("Could not save the result file; the result is shown above.")
        return 1
    print("Result saved as US30_READONLY_RESULT.json beside this launcher.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
