"""Aggregate independent, provenance-verified MT5 DEMO tick sessions.

This is descriptive certification support only. It does not infer execution
quality, profitability, or permission to trade.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.mt5_tick_market_profile import ProfileError, profile_dataset


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ProfileError(f"{label} is missing or invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProfileError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ProfileError(f"{label} must include a timezone")
    return parsed


def _validated_duration(manifest: dict[str, Any], index: int) -> float:
    value = manifest.get("duration_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"session {index}: duration_seconds must be a numeric monotonic measurement")
    if not math.isfinite(value) or value < 0:
        raise ProfileError(f"session {index}: duration_seconds must be finite and non-negative")
    if manifest.get("duration_clock") != "monotonic":
        raise ProfileError(f"session {index}: duration was not measured monotonically")
    if value < 1800:
        raise ProfileError(f"session {index}: collection was shorter than 30 minutes")
    return float(value)


def certify_sessions(sessions: list[tuple[str | Path, str | Path]]) -> dict[str, Any]:
    if len(sessions) < 2:
        raise ProfileError("at least two independent collection sessions are required")

    profiles = []
    hashes = set()
    intervals = []
    for index, (csv_path, manifest_path) in enumerate(sessions, start=1):
        profile = profile_dataset(csv_path, manifest_path)
        digest = profile["sha256"]
        if digest in hashes:
            raise ProfileError("duplicate dataset supplied; sessions must be independent")
        hashes.add(digest)

        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"session {index}: unable to read manifest") from exc
        if not isinstance(manifest, dict):
            raise ProfileError(f"session {index}: manifest root must be an object")

        start = _parse_utc(manifest.get("collection_started_utc"),
                           f"session {index} collection_started_utc")
        end = _parse_utc(manifest.get("collection_ended_utc"),
                         f"session {index} collection_ended_utc")
        if end <= start:
            raise ProfileError(f"session {index}: collection end must follow start")
        duration = _validated_duration(manifest, index)

        intervals.append((start, end, index))
        profiles.append({
            "session": index,
            "sha256": digest,
            "records": profile["records"],
            "started_utc": start.isoformat(),
            "ended_utc": end.isoformat(),
            "duration_seconds": duration,
            "status": profile["status"],
            "symbols": profile["symbols"],
        })

    ordered_intervals = sorted(intervals, key=lambda item: item[0])
    for previous, current in zip(ordered_intervals, ordered_intervals[1:]):
        if current[0] < previous[1]:
            raise ProfileError(
                f"overlapping collection intervals: sessions {previous[2]} and {current[2]}"
            )

    by_symbol: dict[str, Any] = {}
    overall_review = any(p["status"] == "REVIEW" for p in profiles)
    for symbol in ("XAUUSD", "XAGUSD"):
        items = [p["symbols"][symbol] for p in profiles]
        rates = [item["ticks_per_second"] for item in items if item["ticks_per_second"] is not None]
        p95_gaps = [item["intertick_gap_ms_p95"] for item in items
                    if item["intertick_gap_ms_p95"] is not None]
        spreads = [item["spread_points_median"] for item in items]
        gaps_over_5s = sum(item["gaps_over_5s"] for item in items)
        status = "REVIEW" if any(item["status"] == "REVIEW" for item in items) else "PASS"
        by_symbol[symbol] = {
            "status": status,
            "sessions": len(items),
            "total_records": sum(item["records"] for item in items),
            "ticks_per_second_median": round(statistics.median(rates), 4) if rates else None,
            "ticks_per_second_min": round(min(rates), 4) if rates else None,
            "ticks_per_second_max": round(max(rates), 4) if rates else None,
            "intertick_gap_p95_ms_median": round(statistics.median(p95_gaps), 3) if p95_gaps else None,
            "sessions_with_gaps_over_5s": sum(item["gaps_over_5s"] > 0 for item in items),
            "total_gaps_over_5s": gaps_over_5s,
            "session_median_spread_points_min": round(min(spreads), 6),
            "session_median_spread_points_max": round(max(spreads), 6),
            "session_median_spread_points": [round(value, 6) for value in spreads],
            "zero_volume_real_pct_by_session": [item["zero_volume_real_pct"] for item in items],
        }
        overall_review = overall_review or status == "REVIEW"

    return {
        "status": "REVIEW" if overall_review else "PASS",
        "certification_type": "MULTI_SESSION_DESCRIPTIVE_ONLY",
        "sessions": profiles,
        "session_count": len(profiles),
        "symbols": by_symbol,
        "limitations": [
            "A PASS means only that supplied independent sessions passed the configured data-integrity and descriptive gap checks.",
            "This report does not certify live quote availability, spreads under future conditions, slippage, fills, execution quality, or profitability.",
            "No trading authorization is granted; DEMO execution requires a separate risk-controlled implementation and validation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session", action="append", required=True, metavar="CSV=MANIFEST",
        help="one collected session; repeat at least twice",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sessions = []
    for value in args.session:
        if "=" not in value:
            parser.error("--session must use CSV=MANIFEST")
        csv_path, manifest_path = value.split("=", 1)
        if not csv_path or not manifest_path:
            parser.error("--session must include both paths")
        sessions.append((csv_path, manifest_path))
    try:
        result = certify_sessions(sessions)
    except (ProfileError, OSError) as exc:
        parser.exit(2, f"CERTIFICATION FAIL: {exc}\\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
