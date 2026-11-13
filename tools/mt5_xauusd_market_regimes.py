"""Causal, offline XAUUSD market-regime descriptors from tick feature windows.

Regimes are descriptive research labels only. This module never creates trade
signals, labels, orders, or profitability claims.
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
REGIME_SCHEMA = "VELTRIX_XAUUSD_REGIMES_V1"
METRICS = ("realized_volatility_bps", "trend_efficiency", "ticks_per_second")


class RegimeError(ValueError):
    """Raised when feature input is invalid or not research-safe."""


def _number(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegimeError(f"{field} must be a finite number" + (" or null" if nullable else ""))
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RegimeError(f"{field} must be finite")
    return parsed


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _state(value: float, lower: float, upper: float, low_name: str, high_name: str, middle_name: str) -> str:
    if math.isclose(lower, upper, rel_tol=1e-12, abs_tol=1e-12):
        return middle_name
    if value <= lower:
        return low_name
    if value >= upper:
        return high_name
    return middle_name


def _validate_input(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(data, dict):
        raise RegimeError("feature input must be a JSON object")
    if data.get("status") != "PASS" or data.get("research_only") is not True:
        raise RegimeError("input must be a PASS research-only feature dataset")
    if data.get("feature_schema") != FEATURE_SCHEMA or data.get("canonical_symbol") != "XAUUSD":
        raise RegimeError("input must use the supported XAUUSD feature schema")
    digest = data.get("source_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise RegimeError("source_sha256 must be a lowercase SHA-256 digest")
    if isinstance(data.get("source_records"), bool) or not isinstance(data.get("source_records"), int) or data["source_records"] < 1:
        raise RegimeError("source_records must be a positive integer")
    width = data.get("window_seconds")
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 300:
        raise RegimeError("window_seconds must be an integer from 1 to 300")
    rows = data.get("features")
    if not isinstance(rows, list) or data.get("window_count") != len(rows) or not rows:
        raise RegimeError("window_count must match a non-empty features array")
    previous_ms = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RegimeError(f"feature window {index} must be an object")
        if row.get("window_seconds") != width:
            raise RegimeError(f"feature window {index} has inconsistent width")
        try:
            stamp = datetime.fromisoformat(row["window_start_utc"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise RegimeError(f"feature window {index} has an invalid UTC start") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise RegimeError(f"feature window {index} start must be UTC-aware")
        stamp_ms = int(stamp.timestamp() * 1000)
        if stamp_ms % (width * 1000) != 0:
            raise RegimeError(f"feature window {index} is not aligned to UTC epoch boundaries")
        if previous_ms is not None and stamp_ms <= previous_ms:
            raise RegimeError("feature windows must be strictly chronological")
        previous_ms = stamp_ms
        count = row.get("tick_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise RegimeError(f"feature window {index} tick_count must be a positive integer")
        for metric in (*METRICS, "return_bps"):
            _number(row.get(metric), f"feature window {index} {metric}", nullable=True)
        for metric in ("spread_points_median", "spread_points_p95", "spread_points_max"):
            value = _number(row.get(metric), f"feature window {index} {metric}")
            if value < 0:
                raise RegimeError(f"feature window {index} {metric} cannot be negative")
    return rows, width


def classify_regimes(
    data: dict[str, Any],
    *,
    lookback_windows: int = 60,
    min_history: int = 30,
) -> dict[str, Any]:
    """Classify each window using trailing observations strictly before it."""
    if isinstance(lookback_windows, bool) or not isinstance(lookback_windows, int) or not 1 <= lookback_windows <= 300:
        raise RegimeError("lookback_windows must be an integer from 1 to 300")
    if isinstance(min_history, bool) or not isinstance(min_history, int) or not 1 <= min_history <= lookback_windows:
        raise RegimeError("min_history must be an integer from 1 to lookback_windows")
    rows, width = _validate_input(data)
    history: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        prior_rows = history[-lookback_windows:]
        prior = {
            metric: [float(item[metric]) for item in prior_rows if item.get(metric) is not None]
            for metric in METRICS
        }
        available = all(row.get(metric) is not None for metric in METRICS) and row.get("return_bps") is not None
        enough_history = all(len(prior[metric]) >= min_history for metric in METRICS)
        result: dict[str, Any] = {
            "window_start_utc": row["window_start_utc"],
            "tick_count": row["tick_count"],
            "history_count": min((len(prior[m]) for m in METRICS), default=0),
            "history_start_utc": prior_rows[0]["window_start_utc"] if prior_rows and enough_history else None,
            "history_end_utc": prior_rows[-1]["window_start_utc"] if prior_rows else None,
            "volatility_state": None,
            "trend_state": None,
            "activity_state": None,
            "direction": None,
            "regime_label": "WARMUP",
            "classification_basis": "PAST_WINDOWS_ONLY",
            "thresholds": None,
        }
        if enough_history and available:
            thresholds: dict[str, dict[str, float]] = {}
            for metric in METRICS:
                values = prior[metric]
                thresholds[metric] = {
                    "p25": round(_percentile(values, 0.25), 8),
                    "p75": round(_percentile(values, 0.75), 8),
                }
            vol = float(row["realized_volatility_bps"])
            efficiency = float(row["trend_efficiency"])
            activity = float(row["ticks_per_second"])
            result["volatility_state"] = _state(
                vol, thresholds["realized_volatility_bps"]["p25"],
                thresholds["realized_volatility_bps"]["p75"], "LOW", "HIGH", "NORMAL")
            result["trend_state"] = _state(
                efficiency, thresholds["trend_efficiency"]["p25"],
                thresholds["trend_efficiency"]["p75"], "RANGE", "TREND", "MIXED")
            result["activity_state"] = _state(
                activity, thresholds["ticks_per_second"]["p25"],
                thresholds["ticks_per_second"]["p75"], "QUIET", "ACTIVE", "NORMAL")
            change = float(row["return_bps"])
            result["direction"] = "UP" if change > 0 else "DOWN" if change < 0 else "FLAT"
            result["regime_label"] = (
                f"{result['volatility_state']}_VOL_"
                f"{result['trend_state']}_{result['direction']}"
            )
            result["thresholds"] = thresholds
        elif enough_history:
            result["regime_label"] = "UNCLASSIFIED_CURRENT_DATA"
        output.append(result)

        # Append the current observation only after classifying it. Keep nulls
        # in the row history so lookback_windows always means prior windows,
        # not an unbounded search for older non-null observations.
        history.append({
            "window_start_utc": row["window_start_utc"],
            **{metric: row.get(metric) for metric in METRICS},
        })

    return {
        "status": "PASS",
        "research_only": True,
        "regime_schema": REGIME_SCHEMA,
        "canonical_symbol": "XAUUSD",
        "source_feature_schema": FEATURE_SCHEMA,
        "source_sha256": data["source_sha256"],
        "source_records": data["source_records"],
        "window_seconds": width,
        "lookback_windows": lookback_windows,
        "min_history": min_history,
        "window_count": len(output),
        "classified_windows": sum(item["regime_label"] not in ("WARMUP", "UNCLASSIFIED_CURRENT_DATA") for item in output),
        "regimes": output,
        "methodology": "Per-window thresholds use only the preceding min_history..lookback_windows completed windows; current window is appended after classification.",
        "limitations": [
            "Descriptive adaptive regime tags only; not trade signals, recommendations, or execution permission.",
            "Quantile thresholds are session-local and should not be treated as stable market constants.",
            "Warm-up and insufficient-current-data windows remain unclassified.",
            "No future windows, external labels, traded-volume data, or order/fill data are used.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="verified XAUUSD feature-window JSON")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lookback-windows", type=int, default=60)
    parser.add_argument("--min-history", type=int, default=30)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        result = classify_regimes(data, lookback_windows=args.lookback_windows, min_history=args.min_history)
    except (OSError, json.JSONDecodeError, RegimeError) as exc:
        parser.exit(2, f"REGIME RESEARCH FAIL: {exc}\\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
