"""Generate research-only XAUUSD candidate events from preregistered past-only formulas.

No PnL, labels, trade instructions, or broker orders are generated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

from tools.mt5_tick_market_profile import ProfileError, percentile
from tools.mt5_xauusd_feature_research import build_features
from tools.mt5_xauusd_strategy_registry import validate_registry


class CandidateError(ValueError):
    """Raised when feature data or candidate generation inputs are invalid."""


def _finite(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateError(f"{field} must be finite" + (" or null" if nullable else ""))
    number = float(value)
    if not math.isfinite(number):
        raise CandidateError(f"{field} must be finite")
    return number


def _validate_features(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(data, dict) or data.get("status") != "PASS" or data.get("research_only") is not True:
        raise CandidateError("feature input must be PASS and research_only")
    if data.get("feature_schema") != "VELTRIX_XAUUSD_TICK_WINDOWS_V1" or data.get("canonical_symbol") != "XAUUSD":
        raise CandidateError("only verified XAUUSD feature schema is accepted")
    digest = data.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise CandidateError("source_sha256 must be a lowercase SHA-256 digest")
    width = data.get("window_seconds")
    if isinstance(width, bool) or not isinstance(width, int) or width != 5:
        raise CandidateError("candidate engine requires five-second feature windows")
    rows = data.get("features")
    if not isinstance(rows, list) or not rows or data.get("window_count") != len(rows):
        raise CandidateError("window_count must match a non-empty features array")
    source_records = data.get("source_records")
    if isinstance(source_records, bool) or not isinstance(source_records, int) or source_records < 1:
        raise CandidateError("source_records must be a positive integer")
    total_ticks = 0
    previous_ms = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("window_seconds") != width:
            raise CandidateError(f"invalid feature window {index}")
        try:
            stamp = datetime.fromisoformat(row["window_start_utc"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise CandidateError(f"invalid timestamp in feature window {index}") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise CandidateError(f"feature window {index} timestamp must be UTC")
        stamp_ms = int(stamp.timestamp() * 1000)
        if stamp_ms % (width * 1000) != 0 or (previous_ms is not None and stamp_ms <= previous_ms):
            raise CandidateError("feature windows must be aligned and strictly chronological")
        previous_ms = stamp_ms
        count = row.get("tick_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise CandidateError(f"feature window {index} tick_count must be positive")
        total_ticks += count
        close = _finite(row.get("mid_close"), f"window {index} mid_close")
        high = _finite(row.get("mid_high"), f"window {index} mid_high")
        low = _finite(row.get("mid_low"), f"window {index} mid_low")
        if close <= 0 or high <= 0 or low <= 0:
            raise CandidateError(f"window {index} prices must be positive")
        if high < low or close < low or close > high:
            raise CandidateError(f"window {index} has inconsistent OHLC values")
        rv = _finite(row.get("realized_volatility_bps"), f"window {index} realized_volatility_bps", nullable=True)
        if rv is not None and rv < 0:
            raise CandidateError(f"window {index} realized volatility cannot be negative")
    if total_ticks != source_records:
        raise CandidateError("feature tick counts do not reconcile to source_records")
    return rows, width


def _volatility_scale(rows: list[dict[str, Any]], start: int, end: int) -> float | None:
    values = [row.get("realized_volatility_bps") for row in rows[start:end]]
    if not values or any(value is None for value in values):
        return None
    scale = math.sqrt(sum(float(value) ** 2 for value in values))
    return scale if math.isfinite(scale) and scale > 0 else None


def _range_width_bps(rows: list[dict[str, Any]], end_exclusive: int, lookback_windows: int) -> float | None:
    start = end_exclusive - lookback_windows
    if start < 0:
        return None
    prior = rows[start:end_exclusive]
    first_close = float(prior[0]["mid_close"])
    high = max(float(row["mid_high"]) for row in prior)
    low = min(float(row["mid_low"]) for row in prior)
    return (high - low) / first_close * 10000


def _utc_window_end_msc(row: dict[str, Any], width: int) -> int:
    stamp = datetime.fromisoformat(row["window_start_utc"].replace("Z", "+00:00"))
    return int(stamp.timestamp() * 1000) + width * 1000


def _event(
    candidate_id: str,
    family: str,
    row: dict[str, Any],
    index: int,
    width: int,
    direction: str,
    horizon: int,
    parameters: dict[str, Any],
    score: float,
) -> dict[str, Any]:
    parameter_text = ",".join(f"{key}={parameters[key]}" for key in sorted(parameters))
    signal_id = f"{candidate_id}:{index}:{parameter_text}:h={horizon}"
    return {
        "signal_id": signal_id,
        "candidate_id": candidate_id,
        "family": family,
        "signal_window_index": index,
        "signal_window_start_utc": row["window_start_utc"],
        "signal_window_end_msc": _utc_window_end_msc(row, width),
        "direction": direction,
        "horizon_seconds": horizon,
        "parameters": parameters,
        "signal_strength": round(score, 8),
        "event_origin": "CANDIDATE_RESEARCH_SIGNAL_NOT_TRADE",
        "research_only": True,
        "execution_authorized": False,
    }


def generate_candidate_events(features: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    registry_result = validate_registry(registry)
    rows, width = _validate_features(features)
    events: list[dict[str, Any]] = []
    counts = {item["candidate_id"]: 0 for item in registry["candidates"]}
    horizons = registry["evaluation"]["holding_horizons_seconds"]

    for candidate in registry["candidates"]:
        cid = candidate["candidate_id"]
        family = candidate["family"]
        grid = candidate["parameter_grid"]
        if family == "momentum_continuation":
            for lookback, threshold in product(grid["lookback_seconds"], grid["standardized_impulse_threshold"]):
                n = lookback // width
                for index in range(n, len(rows)):
                    scale = _volatility_scale(rows, index - n, index)
                    current = float(rows[index]["mid_close"])
                    previous = float(rows[index - n]["mid_close"])
                    if scale is None or current <= 0 or previous <= 0:
                        continue
                    z = math.log(current / previous) * 10000 / scale
                    if abs(z) < threshold:
                        continue
                    direction = "long" if z > 0 else "short"
                    params = {"lookback_seconds": lookback, "standardized_impulse_threshold": threshold}
                    for horizon in horizons:
                        events.append(_event(cid, family, rows[index], index, width, direction, horizon, params, z))
                        counts[cid] += 1

        elif family == "mean_reversion":
            for lookback, threshold in product(grid["lookback_seconds"], grid["standardized_displacement_threshold"]):
                n = lookback // width
                for index in range(n, len(rows)):
                    scale = _volatility_scale(rows, index - n, index)
                    current = float(rows[index]["mid_close"])
                    reference = sum(float(row["mid_close"]) for row in rows[index - n:index]) / n
                    if scale is None or current <= 0 or reference <= 0:
                        continue
                    z = math.log(current / reference) * 10000 / scale
                    if abs(z) < threshold:
                        continue
                    direction = "short" if z > 0 else "long"
                    params = {"lookback_seconds": lookback, "standardized_displacement_threshold": threshold}
                    for horizon in horizons:
                        events.append(_event(cid, family, rows[index], index, width, direction, horizon, params, abs(z)))
                        counts[cid] += 1

        elif family == "volatility_breakout":
            for lookback, distance_fraction, compression_percentile in product(
                grid["lookback_seconds"],
                grid["breakout_distance_volatility_fraction"],
                grid["compression_reference_percentile"],
            ):
                n = lookback // width
                for index in range(60 + n, len(rows)):
                    scale = _volatility_scale(rows, index - n, index)
                    if scale is None:
                        continue
                    current_range = _range_width_bps(rows, index, n)
                    history = [
                        _range_width_bps(rows, end, n)
                        for end in range(index - 60, index)
                    ]
                    if current_range is None or any(value is None for value in history):
                        continue
                    compression_cutoff = percentile([float(value) for value in history], compression_percentile / 100)
                    if current_range > compression_cutoff:
                        continue
                    prior = rows[index - n:index]
                    prior_high = max(float(row["mid_high"]) for row in prior)
                    prior_low = min(float(row["mid_low"]) for row in prior)
                    current = float(rows[index]["mid_close"])
                    long_distance = math.log(current / prior_high) * 10000 if current > prior_high else 0.0
                    short_distance = math.log(prior_low / current) * 10000 if current < prior_low else 0.0
                    required = distance_fraction * scale
                    direction = "long" if long_distance >= required else ("short" if short_distance >= required else None)
                    if direction is None:
                        continue
                    score = long_distance / scale if direction == "long" else short_distance / scale
                    params = {
                        "lookback_seconds": lookback,
                        "breakout_distance_volatility_fraction": distance_fraction,
                        "compression_reference_percentile": compression_percentile,
                    }
                    for horizon in horizons:
                        events.append(_event(cid, family, rows[index], index, width, direction, horizon, params, score))
                        counts[cid] += 1
        else:
            raise CandidateError(f"unsupported registered candidate family: {family}")

    events.sort(key=lambda item: (
        item["signal_window_end_msc"],
        item["candidate_id"],
        item["signal_id"],
    ))
    source_hash = features["source_sha256"]
    development_hashes = registry["known_development_data"]["source_sha256"]
    data_role = "DEVELOPMENT_ONLY" if source_hash in development_hashes else "UNCLASSIFIED_NOT_HOLDOUT"
    return {
        "status": "PASS",
        "research_only": True,
        "candidate_schema": "VELTRIX_XAUUSD_CANDIDATE_EVENTS_V1",
        "canonical_symbol": "XAUUSD",
        "broker_symbol": features.get("broker_symbol"),
        "source_sha256": source_hash,
        "source_records": features["source_records"],
        "window_seconds": width,
        "window_count": len(rows),
        "data_role": data_role,
        "final_holdout_eligible": False,
        "registry_sha256": registry_result["registry_sha256"],
        "candidate_event_count": len(events),
        "candidate_event_counts": counts,
        "events": events,
        "limitations": [
            "Candidate events are research hypotheses, not trade instructions or approved signals.",
            "No PnL, performance ranking, position sizing, or broker order is generated.",
            "The current source sessions are development-only and never become final holdout data.",
            "All formulas use completed current windows and strictly preceding windows for trailing references and scales.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        features = build_features(args.csv, args.manifest, window_seconds=5)
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        result = generate_candidate_events(features, registry)
    except (OSError, json.JSONDecodeError, CandidateError, ProfileError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"CANDIDATE GENERATION FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
