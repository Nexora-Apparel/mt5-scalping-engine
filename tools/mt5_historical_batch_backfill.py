"""Bounded multi-date historical XAUUSD backfill using the reviewed DEMO probe.

Input is a preregistered JSON list of UTC intervals. Each interval is delegated
to the existing 31-minute read-only probe and gets an independent CSV/manifest.
No order or position-management API is called.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from tools.mt5_xauusd_historical_tick_probe import (
    MAX_PROBE_DURATION_MILLISECONDS,
    parse_utc,
    probe,
)
from tools.mt5_demo_tick_collector import DiagnosticFailure

MAX_INTERVALS = 12
MAX_TOTAL_DURATION_MILLISECONDS = 6 * 60 * 60 * 1000


def validate_interval_plan(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiagnosticFailure("interval plan must be valid JSON") from exc
    if not isinstance(payload, list) or not 1 <= len(payload) <= MAX_INTERVALS:
        raise DiagnosticFailure(f"interval plan must contain 1 to {MAX_INTERVALS} intervals")

    intervals: list[dict[str, Any]] = []
    dates: set[str] = set()
    total_ms = 0
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or set(item) != {"id", "from_utc", "to_utc"}:
            raise DiagnosticFailure(f"interval {index} must contain exactly id, from_utc, to_utc")
        interval_id = item["id"]
        if not isinstance(interval_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", interval_id):
            raise DiagnosticFailure(f"interval {index} has an invalid id")
        start, end = parse_utc(item["from_utc"]), parse_utc(item["to_utc"])
        if start.microsecond % 1000 or end.microsecond % 1000:
            raise DiagnosticFailure(f"interval {interval_id} must use millisecond-aligned timestamps")
        duration_ms = int((end - start).total_seconds() * 1000)
        if duration_ms <= 0 or duration_ms > MAX_PROBE_DURATION_MILLISECONDS:
            raise DiagnosticFailure(f"interval {interval_id} must be positive and no longer than 31 minutes")
        date_key = start.date().isoformat()
        if date_key in dates:
            raise DiagnosticFailure("each historical interval must use a distinct UTC date")
        dates.add(date_key)
        intervals.append({
            "id": interval_id,
            "from_utc": start.isoformat().replace("+00:00", "Z"),
            "to_utc": end.isoformat().replace("+00:00", "Z"),
            "utc_date": date_key,
            "duration_milliseconds": duration_ms,
        })
        total_ms += duration_ms

    if total_ms > MAX_TOTAL_DURATION_MILLISECONDS:
        raise DiagnosticFailure("total requested historical duration exceeds the six-hour batch limit")
    intervals.sort(key=lambda x: x["from_utc"])
    for previous, current in zip(intervals, intervals[1:]):
        if current["from_utc"] <= previous["to_utc"]:
            raise DiagnosticFailure("historical intervals overlap or are not strictly chronological")
    return intervals


def run_batch(mt5: Any, intervals: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    provenance = {
        "source_ref": os.environ.get("VELTRIX_SOURCE_REF", "").strip(),
        "source_commit": os.environ.get("VELTRIX_SOURCE_COMMIT", "").strip(),
        "dispatcher_commit": os.environ.get("GITHUB_SHA", "").strip(),
        "installer_signer_thumbprint": os.environ.get("MT5_INSTALLER_SIGNER_THUMBPRINT", "").strip(),
    }
    if not provenance["source_ref"]:
        raise DiagnosticFailure("required provenance field is missing: source_ref")
    for key in ("source_commit", "dispatcher_commit", "installer_signer_thumbprint"):
        if not re.fullmatch(r"[0-9a-fA-F]{40}", provenance[key]):
            raise DiagnosticFailure(f"required provenance field is missing or malformed: {key}")

    output_dir.mkdir(parents=True, exist_ok=True)
    plan_bytes = json.dumps(intervals, sort_keys=True, separators=(",", ":")).encode()
    manifest: dict[str, Any] = {
        "schema": "VELTRIX_XAUUSD_HISTORICAL_BATCH_V1",
        "status": "RUNNING",
        "source_type": "authenticated_exness_mt5_demo_terminal_historical_ticks",
        "retrieved_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "source_ref": provenance["source_ref"],
        "source_commit": provenance["source_commit"],
        "dispatcher_commit": provenance["dispatcher_commit"],
        "installer_signer_thumbprint": provenance["installer_signer_thumbprint"],
        "account_mode_required": "DEMO",
        "canonical_symbol": "XAUUSD",
        "trading_enabled": False,
        "order_submission": False,
        "position_management": False,
        "interval_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "interval_count": len(intervals),
        "total_requested_duration_milliseconds": sum(x["duration_milliseconds"] for x in intervals),
        "intervals": [],
        "interpretation": "Historical quotes are retrospective observations, not actual broker fills or prospective live sessions.",
    }
    manifest_path = output_dir / "batch_manifest.json"
    try:
        for item in intervals:
            result = probe(
                mt5,
                parse_utc(item["from_utc"]),
                parse_utc(item["to_utc"]),
                output_dir / item["id"],
            )
            manifest["intervals"].append({
                **item,
                "status": result["status"],
                "records": result["records"],
                "first_tick_utc": result["first_tick_utc"],
                "last_tick_utc": result["last_tick_utc"],
                "broker_symbol": result["broker_symbol"],
                "account_mode": result["account_mode"],
                "dataset_sha256": result["sha256"],
                "dataset_audit": result["dataset_audit"],
                "manifest_path": f'{item["id"]}/manifest.json',
                "csv_path": f'{item["id"]}/xauusd_historical_ticks.csv',
            })
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest["status"] = "PASS"
    except Exception as exc:
        manifest["status"] = "FAIL"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intervals-json", required=True, help="JSON array of preregistered UTC intervals")
    parser.add_argument("--output-dir", type=Path, default=Path("historical-batch"))
    args = parser.parse_args()
    try:
        intervals = validate_interval_plan(args.intervals_json)
        import MetaTrader5 as mt5
        result = run_batch(mt5, intervals, args.output_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (DiagnosticFailure, ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
