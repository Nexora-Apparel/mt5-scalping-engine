"""Generate preregistered, past-only XAUUSD candidate events from verified features.

Offline research only. This module does not send orders or evaluate outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.mt5_xauusd_strategy_registry import RegistryError, validate_registry
from tools.mt5_tick_market_profile import percentile


class SignalError(ValueError):
    """Raised when feature or registry inputs violate the signal contract."""


CANDIDATE_IDS = {
    "XAU_MOMENTUM_CONTINUATION_V1",
    "XAU_MEAN_REVERSION_V1",
    "XAU_VOLATILITY_BREAKOUT_V1",
}


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise SignalError(f"{field} must be a finite number")
    return float(value)


def _utc_epoch_ms(value: Any) -> int:
    if not isinstance(value, str):
        raise SignalError("window_start_utc must be an ISO-8601 string")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SignalError("window_start_utc is invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise SignalError("window_start_utc must include a timezone")
    return int(stamp.timestamp() * 1000)


def _validate_features(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(data, dict) or data.get("status") != "PASS" or data.get("research_only") is not True:
        raise SignalError("feature input must be a PASS research-only object")
    if data.get("canonical_symbol") != "XAUUSD":
        raise SignalError("only canonical XAUUSD feature data is permitted")
    if data.get("feature_schema") != "VELTRIX_XAUUSD_TICK_WINDOWS_V1":
        raise SignalError("unsupported feature schema")
    width = data.get("window_seconds")
    if isinstance(width, bool) or width != 5:
        raise SignalError("candidate registry requires five-second feature windows")
    digest = data.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise SignalError("source_sha256 must be a lowercase SHA-256 digest")
    windows = data.get("features")
    if not isinstance(windows, list) or not windows:
        raise SignalError("features must be a non-empty array")
    if data.get("window_count") != len(windows):
        raise SignalError("window_count does not reconcile with feature rows")
    expected = width * 1000
    previous = None
    normalized = []
    for index, row in enumerate(windows):
        if not isinstance(row, dict) or row.get("window_seconds") != width:
            raise SignalError(f"feature row {index} has an incompatible window width")
        start = _utc_epoch_ms(row.get("window_start_utc"))
        if previous is not None and start <= previous:
            raise SignalError("feature windows must be strictly chronological and unique")
        previous = start
        normalized.append({**row, "_start_msc": start, "_end_msc": start + expected})
    return normalized, width


def _consecutive(rows: list[dict[str, Any]], start: int, end: int, width_ms: int) -> bool:
    if start < 0 or end > len(rows) or start >= end:
        return False
    return all(rows[i]["_start_msc"] - rows[i - 1]["_start_msc"] == width_ms
               for i in range(start + 1, end))


def _number(row: dict[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value is None:
        return None
    return _finite(value, field)


def _scale(rows: list[dict[str, Any]], start: int, end: int) -> float | None:
    values = [_number(rows[i], "realized_volatility_bps") for i in range(start, end)]
    if not values or any(value is None for value in values):
        return None
    result = math.sqrt(sum(value * value for value in values if value is not None))
    return result if math.isfinite(result) and result > 0 else None


def _signal_id(source_sha: str, candidate_id: str, window_end: int, direction: str,
               parameters: dict[str, Any]) -> str:
    raw = json.dumps([source_sha, candidate_id, window_end, direction, parameters],
                     sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def generate_candidate_events(features: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Generate candidate events using only the current completed window and prior windows."""
    try:
        registry_result = validate_registry(registry)
    except RegistryError as exc:
        raise SignalError(f"strategy registry rejected: {exc}") from exc
    rows, width = _validate_features(features)
    candidates = {item["candidate_id"]: item for item in registry["candidates"]}
    if set(candidates) != CANDIDATE_IDS:
        raise SignalError("candidate registry does not match the three frozen XAUUSD families")

    width_ms = width * 1000
    source_sha = features["source_sha256"]
    events: list[dict[str, Any]] = []
    evaluated = 0
    skipped = {"incomplete_history": 0, "missing_features": 0, "zero_scale": 0, "no_trigger": 0}

    def emit(candidate_id: str, row: dict[str, Any], direction: str,
             horizon: int, parameters: dict[str, Any], score: float) -> None:
        end_msc = row["_end_msc"]
        events.append({
            "signal_id": _signal_id(source_sha, candidate_id, end_msc, direction, parameters),
            "candidate_id": candidate_id,
            "signal_window_end_msc": end_msc,
            "direction": direction,
            "horizon_seconds": horizon,
            "event_origin": "PREREGISTERED_PAST_ONLY_FEATURE_SIGNAL",
            "source_sha256": source_sha,
            "feature_window_start_msc": row["_start_msc"],
            "standardized_score": round(score, 10),
            "parameters": parameters,
            "research_only": True,
            "execution_sent": False,
        })

    for i, current in enumerate(rows):
        evaluated += 1
        close = _number(current, "mid_close")
        high = _number(current, "mid_high")
        low = _number(current, "mid_low")
        if close is None or high is None or low is None or min(close, low) <= 0 or high < low:
            skipped["missing_features"] += 1
            continue

        # Momentum: current close versus the close exactly L seconds earlier;
        # volatility scale uses only the L/5 completed windows before current.
        spec = candidates["XAU_MOMENTUM_CONTINUATION_V1"]
        for lookback in spec["parameter_grid"]["lookback_seconds"]:
            n = lookback // width
            start = i - n
            if start < 0 or not _consecutive(rows, start, i + 1, width_ms):
                skipped["incomplete_history"] += 1
                continue
            prior_close = _number(rows[start], "mid_close")
            scale = _scale(rows, start, i)
            if prior_close is None or prior_close <= 0:
                skipped["missing_features"] += 1
                continue
            if scale is None:
                skipped["zero_scale"] += 1
                continue
            z = (10000.0 * math.log(close / prior_close)) / scale
            for threshold in spec["parameter_grid"]["standardized_impulse_threshold"]:
                if abs(z) >= threshold:
                    direction = "long" if z > 0 else "short"
                    params = {"lookback_seconds": lookback, "standardized_impulse_threshold": threshold}
                    for horizon in spec["horizons_seconds"]:
                        emit(spec["candidate_id"], current, direction, horizon, params, z)
                else:
                    skipped["no_trigger"] += 1

        # Mean reversion: prior-window arithmetic mean and prior-only volatility.
        spec = candidates["XAU_MEAN_REVERSION_V1"]
        for lookback in spec["parameter_grid"]["lookback_seconds"]:
            n = lookback // width
            start = i - n
            if start < 0 or not _consecutive(rows, start, i + 1, width_ms):
                skipped["incomplete_history"] += 1
                continue
            prior_closes = [_number(rows[j], "mid_close") for j in range(start, i)]
            scale = _scale(rows, start, i)
            if any(value is None or value <= 0 for value in prior_closes):
                skipped["missing_features"] += 1
                continue
            if scale is None:
                skipped["zero_scale"] += 1
                continue
            reference = sum(value for value in prior_closes if value is not None) / n
            z = (10000.0 * math.log(close / reference)) / scale
            for threshold in spec["parameter_grid"]["standardized_displacement_threshold"]:
                if abs(z) >= threshold:
                    direction = "short" if z > 0 else "long"
                    params = {"lookback_seconds": lookback, "standardized_displacement_threshold": threshold}
                    for horizon in spec["horizons_seconds"]:
                        emit(spec["candidate_id"], current, direction, horizon, params, z)
                else:
                    skipped["no_trigger"] += 1

        # Breakout: prior range and scale exclude current; compression reference
        # consists of 60 rolling ranges, each built only from windows preceding it.
        spec = candidates["XAU_VOLATILITY_BREAKOUT_V1"]
        for lookback in spec["parameter_grid"]["lookback_seconds"]:
            n = lookback // width
            start = i - n
            compression_start = i - 60
            if start < 0 or compression_start - n < 0 or not _consecutive(rows, compression_start - n, i + 1, width_ms):
                skipped["incomplete_history"] += 1
                continue
            scale = _scale(rows, start, i)
            prior_highs = [_number(rows[j], "mid_high") for j in range(start, i)]
            prior_lows = [_number(rows[j], "mid_low") for j in range(start, i)]
            first_close = _number(rows[start], "mid_close")
            if scale is None:
                skipped["zero_scale"] += 1
                continue
            if any(v is None for v in prior_highs + prior_lows) or first_close is None or first_close <= 0:
                skipped["missing_features"] += 1
                continue
            prior_high = max(v for v in prior_highs if v is not None)
            prior_low = min(v for v in prior_lows if v is not None)
            current_range_bps = (prior_high - prior_low) / first_close * 10000.0
            historical_ranges = []
            valid_history = True
            for j in range(i - 60, i):
                range_start = j - n
                if not _consecutive(rows, range_start, j, width_ms):
                    valid_history = False
                    break
                h = [_number(rows[k], "mid_high") for k in range(range_start, j)]
                l = [_number(rows[k], "mid_low") for k in range(range_start, j)]
                base = _number(rows[range_start], "mid_close")
                if any(v is None for v in h + l) or base is None or base <= 0:
                    valid_history = False
                    break
                historical_ranges.append((max(v for v in h if v is not None) -
                                          min(v for v in l if v is not None)) / base * 10000.0)
            if not valid_history or len(historical_ranges) != 60:
                skipped["incomplete_history"] += 1
                continue
            for compression_pct in spec["parameter_grid"]["compression_reference_percentile"]:
                compression_limit = percentile(historical_ranges, compression_pct / 100.0)
                if compression_limit is None or current_range_bps > compression_limit:
                    skipped["no_trigger"] += len(spec["parameter_grid"]["breakout_distance_volatility_fraction"])
                    continue
                up = 10000.0 * math.log(close / prior_high) if close > prior_high else 0.0
                down = 10000.0 * math.log(prior_low / close) if close < prior_low else 0.0
                for fraction in spec["parameter_grid"]["breakout_distance_volatility_fraction"]:
                    distance = fraction * scale
                    if up >= distance:
                        direction, score = "long", up / scale
                    elif down >= distance:
                        direction, score = "short", down / scale
                    else:
                        skipped["no_trigger"] += 1
                        continue
                    params = {"lookback_seconds": lookback,
                              "breakout_distance_volatility_fraction": fraction,
                              "compression_reference_percentile": compression_pct}
                    for horizon in spec["horizons_seconds"]:
                        emit(spec["candidate_id"], current, direction, horizon, params, score)

    events.sort(key=lambda event: (event["signal_window_end_msc"], event["candidate_id"],
                                   json.dumps(event["parameters"], sort_keys=True), event["horizon_seconds"]))
    ids = [event["signal_id"] for event in events]
    if len(ids) != len(set(ids)):
        raise SignalError("generated signal identifiers are not unique")
    return {
        "status": "PASS",
        "research_only": True,
        "canonical_symbol": "XAUUSD",
        "feature_schema": features["feature_schema"],
        "source_sha256": source_sha,
        "registry_sha256": registry_result["registry_sha256"],
        "registry_schema": registry_result["registry_schema"],
        "evaluated_windows": evaluated,
        "signal_count": len(events),
        "skip_counts": skipped,
        "events": events,
        "limitations": [
            "Candidate events are generated from frozen formulas and past-only completed windows; they are not trade recommendations.",
            "The output is for deterministic replay only; it does not submit, stage, or authorize orders.",
            "Sessions 8 and 9 are development-only and cannot be used as validation or final holdout evidence.",
            "Commission remains unverified; no net-performance or candidate approval claim is permitted.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        features = json.loads(args.features.read_text(encoding="utf-8"))
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        result = generate_candidate_events(features, registry)
    except (OSError, json.JSONDecodeError, RegistryError, SignalError) as exc:
        parser.exit(2, f"CANDIDATE SIGNAL GENERATION FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
