"""Descriptive cross-session diagnostics for verified XAUUSD tick feature windows.

This tool checks provenance and compares feature distributions. It does not
select strategies, infer profitability, or generate trading signals.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEATURE_SCHEMA = "VELTRIX_XAUUSD_TICK_WINDOWS_V1"
DIAGNOSTIC_SCHEMA = "VELTRIX_XAUUSD_CROSS_SESSION_DIAGNOSTICS_V1"
METRICS = (
    "tick_count", "ticks_per_second", "return_bps", "range_bps",
    "realized_volatility_bps", "trend_efficiency",
    "spread_points_median", "spread_points_p95", "spread_points_max",
    "max_intertick_gap_ms", "gaps_over_1s", "mid_price_change_ratio",
)
CORRELATION_METRICS = (
    "realized_volatility_bps", "trend_efficiency", "ticks_per_second",
    "range_bps", "spread_points_median",
)


class DiagnosticsError(ValueError):
    """Raised when a feature session is invalid or incomparable."""


def _finite(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DiagnosticsError(f"{field} must be finite" + (" or null" if nullable else ""))
    number = float(value)
    if not math.isfinite(number):
        raise DiagnosticsError(f"{field} must be finite")
    return number


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    centered_left = [x - mean_left for x in left]
    centered_right = [x - mean_right for x in right]
    sum_left = sum(x * x for x in centered_left)
    sum_right = sum(x * x for x in centered_right)
    if sum_left <= 0 or sum_right <= 0:
        return None
    covariance = sum(a * b for a, b in zip(centered_left, centered_right))
    return round(covariance / math.sqrt(sum_left * sum_right), 8)


def _load_session(data: dict[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise DiagnosticsError(f"{label}: input must be a JSON object")
    if data.get("status") != "PASS" or data.get("research_only") is not True:
        raise DiagnosticsError(f"{label}: input must be PASS and research_only")
    if data.get("feature_schema") != FEATURE_SCHEMA or data.get("canonical_symbol") != "XAUUSD":
        raise DiagnosticsError(f"{label}: only the supported XAUUSD feature schema is accepted")
    digest = data.get("source_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise DiagnosticsError(f"{label}: invalid source SHA-256")
    records = data.get("source_records")
    if isinstance(records, bool) or not isinstance(records, int) or records < 1:
        raise DiagnosticsError(f"{label}: source_records must be a positive integer")
    width = data.get("window_seconds")
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 300:
        raise DiagnosticsError(f"{label}: invalid window_seconds")
    rows = data.get("features")
    if not isinstance(rows, list) or not rows or data.get("window_count") != len(rows):
        raise DiagnosticsError(f"{label}: window_count must match a non-empty features array")
    previous_ms = None
    total_ticks = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("window_seconds") != width:
            raise DiagnosticsError(f"{label}: invalid feature window {index}")
        try:
            stamp = datetime.fromisoformat(row["window_start_utc"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise DiagnosticsError(f"{label}: invalid UTC timestamp in window {index}") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise DiagnosticsError(f"{label}: window {index} timestamp must be UTC")
        stamp_ms = int(stamp.timestamp() * 1000)
        if stamp_ms % (width * 1000) != 0 or (previous_ms is not None and stamp_ms <= previous_ms):
            raise DiagnosticsError(f"{label}: windows must be aligned and strictly chronological")
        previous_ms = stamp_ms
        count = row.get("tick_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise DiagnosticsError(f"{label}: invalid tick_count in window {index}")
        total_ticks += count
        for metric in METRICS:
            _finite(row.get(metric), f"{label} window {index} {metric}", nullable=True)
        for metric in ("realized_volatility_bps", "spread_points_median", "spread_points_p95", "spread_points_max"):
            value = row.get(metric)
            if value is not None and value < 0:
                raise DiagnosticsError(f"{label}: {metric} cannot be negative")
        for metric in ("trend_efficiency", "mid_price_change_ratio"):
            value = row.get(metric)
            if value is not None and not 0 <= value <= 1:
                raise DiagnosticsError(f"{label}: {metric} must be between 0 and 1")
    if total_ticks != records:
        raise DiagnosticsError(f"{label}: feature tick counts do not reconcile to source_records")
    first = datetime.fromisoformat(rows[0]["window_start_utc"].replace("Z", "+00:00"))
    last = datetime.fromisoformat(rows[-1]["window_start_utc"].replace("Z", "+00:00"))
    return {
        "sha256": digest,
        "source_records": records,
        "window_seconds": width,
        "rows": rows,
        "start": first,
        "end_exclusive": last.timestamp() + width,
        "start_utc": first.isoformat(),
        "end_utc": datetime.fromtimestamp(last.timestamp() + width, timezone.utc).isoformat(),
    }


def diagnose_sessions(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(sessions, list) or not 2 <= len(sessions) <= 10:
        raise DiagnosticsError("provide between 2 and 10 independent feature sessions")
    loaded = [_load_session(item, f"session_{index + 1}") for index, item in enumerate(sessions)]
    hashes = [item["sha256"] for item in loaded]
    if len(set(hashes)) != len(hashes):
        raise DiagnosticsError("sessions must have unique source SHA-256 hashes")
    widths = {item["window_seconds"] for item in loaded}
    if len(widths) != 1:
        raise DiagnosticsError("all sessions must use the same feature window width")
    loaded.sort(key=lambda item: item["start"])
    for previous, current in zip(loaded, loaded[1:]):
        if previous["end_exclusive"] > current["start"].timestamp():
            raise DiagnosticsError("feature sessions overlap in UTC time")

    session_reports = []
    metric_medians: dict[str, list[float | None]] = {metric: [] for metric in METRICS}
    for index, session in enumerate(loaded, start=1):
        rows = session["rows"]
        summaries: dict[str, Any] = {}
        for metric in METRICS:
            values = [float(row[metric]) for row in rows if row.get(metric) is not None]
            metric_medians[metric].append(statistics_median(values) if values else None)
            summaries[metric] = {
                "observations": len(values),
                "null_count": len(rows) - len(values),
                "min": round(min(values), 8) if values else None,
                "p05": round(_percentile(values, 0.05), 8) if values else None,
                "median": round(_percentile(values, 0.50), 8) if values else None,
                "p95": round(_percentile(values, 0.95), 8) if values else None,
                "max": round(max(values), 8) if values else None,
            }
        correlations: dict[str, dict[str, float | None]] = {}
        for left_metric in CORRELATION_METRICS:
            correlations[left_metric] = {}
            for right_metric in CORRELATION_METRICS:
                pairs = [(row.get(left_metric), row.get(right_metric)) for row in rows]
                valid = [(float(a), float(b)) for a, b in pairs if a is not None and b is not None]
                correlations[left_metric][right_metric] = _correlation(
                    [pair[0] for pair in valid], [pair[1] for pair in valid]
                )
        session_reports.append({
            "session_index": index,
            "source_sha256": session["sha256"],
            "source_records": session["source_records"],
            "window_count": len(rows),
            "start_utc": session["start_utc"],
            "end_utc_exclusive": session["end_utc"],
            "metrics": summaries,
            "pearson_correlations": correlations,
        })

    comparisons = {}
    for metric, medians in metric_medians.items():
        baseline = medians[0]
        comparisons[metric] = {
            "session_medians": medians,
            "median_deltas_from_session_1": [
                round(value - baseline, 8) if value is not None and baseline is not None else None
                for value in medians
            ],
            "relative_median_deltas_pct_from_session_1": [
                round((value - baseline) / abs(baseline) * 100, 6)
                if value is not None and baseline is not None and abs(baseline) > 1e-3
                else None
                for value in medians
            ],
        }
    return {
        "status": "PASS",
        "research_only": True,
        "diagnostic_schema": DIAGNOSTIC_SCHEMA,
        "canonical_symbol": "XAUUSD",
        "window_seconds": loaded[0]["window_seconds"],
        "session_count": len(loaded),
        "total_source_records": sum(item["source_records"] for item in loaded),
        "total_windows": sum(len(item["rows"]) for item in loaded),
        "sessions": session_reports,
        "cross_session_median_comparison": comparisons,
        "limitations": [
            "Descriptive cross-session stability diagnostics only; not a strategy or profitability test.",
            "Sessions remain separate; differences can reflect different market conditions and feed states.",
            "Correlations are contemporaneous descriptive associations, not causal effects.",
            "No traded volume, order fills, slippage, or execution quality is inferred.",
            "No thresholds in this report are used to generate trade permission or signals.",
        ],
    }


def statistics_median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        sessions = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
        result = diagnose_sessions(sessions)
    except (OSError, json.JSONDecodeError, DiagnosticsError) as exc:
        parser.exit(2, f"FEATURE DIAGNOSTICS FAIL: {exc}\\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
