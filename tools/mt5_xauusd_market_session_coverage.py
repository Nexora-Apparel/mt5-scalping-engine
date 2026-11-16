"""Build an immutable-source, timezone-aware XAUUSD market-session coverage report.

This is supplemental descriptive evidence only. It does not alter Phase 8 intake,
the preregistered validation plan, strategy parameters, or execution permissions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CLASSIFIER_VERSION = "1.0.0"
REPORT_SCHEMA = "VELTRIX_XAUUSD_MARKET_SESSION_COVERAGE_V1"
UTC = timezone.utc
SESSIONS = {
    "asian": ("Asia/Tokyo", time(9, 0), time(18, 0)),
    "london": ("Europe/London", time(8, 0), time(17, 0)),
    "new_york": ("America/New_York", time(8, 0), time(17, 0)),
}


class SessionCoverageError(ValueError):
    """Raised when source evidence cannot be safely classified."""


def _parse_aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise SessionCoverageError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SessionCoverageError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SessionCoverageError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise SessionCoverageError(f"IANA timezone data unavailable for {name}") from exc


def _intervals(name: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    zone_name, local_start, local_end = SESSIONS[name]
    zone = _zone(zone_name)
    first = (start.astimezone(zone).date() - timedelta(days=1))
    last = end.astimezone(zone).date() + timedelta(days=1)
    result = []
    day = first
    while day <= last:
        left = datetime.combine(day, local_start, zone).astimezone(UTC)
        right = datetime.combine(day, local_end, zone).astimezone(UTC)
        if right > left:
            result.append((left, right))
        day += timedelta(days=1)
    return result


def _intersections(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    clipped = [(max(left, start), min(right, end)) for left, right in intervals]
    clipped = sorted((left, right) for left, right in clipped if right > left)
    merged: list[tuple[datetime, datetime]] = []
    for left, right in clipped:
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def _seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    return round(sum((right - left).total_seconds() for left, right in intervals), 3)


def _tick_labels(stamp: datetime) -> dict[str, bool]:
    local = {name: stamp.astimezone(_zone(zone_name)) for name, (zone_name, _, _) in SESSIONS.items()}
    labels = {}
    for name, (_, start, end) in SESSIONS.items():
        clock = local[name].timetz().replace(tzinfo=None)
        labels[name] = start <= clock < end
    labels["london_new_york_overlap"] = labels["london"] and labels["new_york"]
    return labels


def _tzdb_version() -> str:
    try:
        return importlib.metadata.version("tzdata")
    except importlib.metadata.PackageNotFoundError:
        return "system-zoneinfo-unknown-version"


def build_report(
    manifest: dict[str, Any],
    csv_path: Path,
    *,
    source_artifact_id: str | None = None,
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise SessionCoverageError("manifest must be a JSON object")
    if manifest.get("canonical_symbol", "XAUUSD") != "XAUUSD":
        raise SessionCoverageError("only canonical XAUUSD evidence is supported")
    if manifest.get("status") != "PASS" or manifest.get("data_audit_status") != "PASS":
        raise SessionCoverageError("source manifest must have PASS collection and data-audit statuses")
    start = _parse_aware(manifest.get("collection_started_utc"), "collection_started_utc")
    end = _parse_aware(manifest.get("collection_ended_utc"), "collection_ended_utc")
    if end <= start:
        raise SessionCoverageError("collection end must be later than collection start")

    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if manifest.get("sha256") != digest:
        raise SessionCoverageError("CSV SHA-256 does not match source manifest")

    counts = {name: 0 for name in (*SESSIONS, "london_new_york_overlap")}
    first_tick: dict[str, str | None] = {name: None for name in counts}
    last_tick: dict[str, str | None] = {name: None for name in counts}
    tick_count = 0
    previous_ms: int | None = None
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"canonical_symbol", "time_msc", "time_utc"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SessionCoverageError("CSV must contain canonical_symbol, time_msc, and time_utc")
        for line_number, row in enumerate(reader, start=2):
            if row.get("canonical_symbol") != "XAUUSD":
                raise SessionCoverageError(f"row {line_number}: non-XAUUSD record in source CSV")
            try:
                stamp_ms = int(row["time_msc"])
            except (TypeError, ValueError) as exc:
                raise SessionCoverageError(f"row {line_number}: invalid time_msc") from exc
            if stamp_ms < 0 or (previous_ms is not None and stamp_ms < previous_ms):
                raise SessionCoverageError(f"row {line_number}: timestamps must be non-negative and monotonic")
            stamp = _parse_aware(row["time_utc"], f"row {line_number} time_utc")
            if int(stamp.timestamp() * 1000) != stamp_ms:
                raise SessionCoverageError(f"row {line_number}: time_utc and time_msc disagree")
            if stamp < start - timedelta(seconds=1) or stamp > end + timedelta(seconds=1):
                raise SessionCoverageError(f"row {line_number}: tick lies outside manifest collection bounds")
            labels = _tick_labels(stamp)
            iso = stamp.isoformat().replace("+00:00", "Z")
            for name, included in labels.items():
                if included:
                    counts[name] += 1
                    first_tick[name] = first_tick[name] or iso
                    last_tick[name] = iso
            tick_count += 1
            previous_ms = stamp_ms

    if tick_count == 0:
        raise SessionCoverageError("source CSV contains no tick records")

    intervals = {name: _intervals(name, start, end) for name in SESSIONS}
    overlap_intervals = []
    for london_left, london_right in intervals["london"]:
        for ny_left, ny_right in intervals["new_york"]:
            left, right = max(london_left, ny_left), min(london_right, ny_right)
            if right > left:
                overlap_intervals.append((left, right))
    intervals["london_new_york_overlap"] = overlap_intervals

    coverage = {}
    for name, spans in intervals.items():
        intersections = _intersections(spans, start, end)
        coverage[name] = {
            "window_intersection_seconds": _seconds(intersections),
            "window_intersections_utc": [
                {"start": left.isoformat().replace("+00:00", "Z"),
                 "end": right.isoformat().replace("+00:00", "Z")}
                for left, right in intersections
            ],
            "tick_count": counts[name],
            "first_tick_utc": first_tick[name],
            "last_tick_utc": last_tick[name],
        }

    try:
        duration = float(manifest["duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionCoverageError("manifest duration_seconds must be numeric") from exc
    if duration <= 0:
        raise SessionCoverageError("manifest duration_seconds must be positive")

    return {
        "status": "PASS",
        "research_only": True,
        "report_schema": REPORT_SCHEMA,
        "classifier_version": CLASSIFIER_VERSION,
        "timezone_database": _tzdb_version(),
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": {
            "session_id": manifest.get("session_id"),
            "source_artifact_id": source_artifact_id or manifest.get("artifact_id"),
            "workflow_run_id": workflow_run_id or manifest.get("workflow_run_id"),
            "canonical_symbol": "XAUUSD",
            "collection_started_utc": start.isoformat().replace("+00:00", "Z"),
            "collection_ended_utc": end.isoformat().replace("+00:00", "Z"),
            "duration_seconds": duration,
            "csv_sha256": digest,
            "tick_count": tick_count,
        },
        "session_coverage": coverage,
        "methodology": "IANA timezone-aware local windows; intervals are start-inclusive/end-exclusive; London-New York overlap is the UTC intersection of the London and New York windows.",
        "limitations": [
            "Supplemental descriptive evidence only; not a Phase 8 intake gate.",
            "Session windows are research proxies, not exchange guarantees or uniform-liquidity claims.",
            "Tick counts are quote observations, not traded volume or execution fills.",
            "This report does not alter raw CSV files, manifests, validation dates, or strategy permissions.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-artifact-id")
    parser.add_argument("--workflow-run-id")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = build_report(
            manifest,
            args.csv,
            source_artifact_id=args.source_artifact_id,
            workflow_run_id=args.workflow_run_id,
        )
    except (OSError, json.JSONDecodeError, SessionCoverageError) as exc:
        parser.exit(2, f"SESSION COVERAGE REPORT BLOCKED: {exc}\n")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "tick_count": report["source"]["tick_count"],
                      "research_only": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
