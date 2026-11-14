"""Convert preregistered candidate signals into a separate multi-position scalp grid.

The adapter creates research event proposals only. It uses past-only volatility
for adaptive SL/TP distances and excludes the legacy five-second horizon.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any


class MultiPositionAdapterError(ValueError):
    pass


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise MultiPositionAdapterError(f"{field} must be finite and positive")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MultiPositionAdapterError(f"{field} must be finite and positive") from exc
    if not math.isfinite(number) or number <= 0:
        raise MultiPositionAdapterError(f"{field} must be finite and positive")
    return number


def _tick_ceil(distance: float, tick_size: float) -> float:
    steps = math.ceil(distance / tick_size - 1e-12)
    return round(steps * tick_size, 10)


def _validate_payload(features: dict[str, Any], candidates: dict[str, Any],
                      broker: dict[str, Any], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    if features.get("status") != "PASS" or features.get("research_only") is not True:
        raise MultiPositionAdapterError("features must be PASS and research_only")
    if candidates.get("status") != "PASS" or candidates.get("research_only") is not True:
        raise MultiPositionAdapterError("candidate events must be PASS and research_only")
    if features.get("canonical_symbol") != "XAUUSD" or candidates.get("canonical_symbol") != "XAUUSD":
        raise MultiPositionAdapterError("only canonical XAUUSD inputs are accepted")
    if features.get("source_sha256") != candidates.get("source_sha256"):
        raise MultiPositionAdapterError("feature and candidate source hashes do not match")
    if broker.get("account_mode", "DEMO") != "DEMO" or broker.get("trading_enabled", False) is not False:
        raise MultiPositionAdapterError("broker snapshot must prove DEMO and trading-disabled")
    if policy.get("status") != "PREREGISTERED_RESEARCH_ONLY" or policy.get("execution_enabled") is not False:
        raise MultiPositionAdapterError("multi-position policy must be preregistered and research-only")
    spec = broker.get("instrument_specs", {}).get("XAUUSD", broker)
    values = {
        "point_size": _positive(spec.get("point_size", spec.get("point")), "point_size"),
        "tick_size": _positive(spec.get("tick_size"), "tick_size"),
    }
    stops = spec.get("stops_level_points", 0)
    if isinstance(stops, bool) or not isinstance(stops, (int, float)) or not math.isfinite(float(stops)) or stops < 0:
        raise MultiPositionAdapterError("stops_level_points must be finite and nonnegative")
    values["minimum_stop_distance"] = float(stops) * values["point_size"]
    rows = features.get("features")
    if not isinstance(rows, list) or not rows:
        raise MultiPositionAdapterError("features array is missing")
    events = candidates.get("events")
    if not isinstance(events, list):
        raise MultiPositionAdapterError("candidate events array is missing")
    return rows, values


def build_multi_position_events(features: dict[str, Any], candidates: dict[str, Any],
                                broker: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    rows, spec = _validate_payload(features, candidates, broker, policy)
    horizons = policy.get("holding_seconds")
    stop_grid = policy.get("stop_volatility_multipliers")
    reward_grid = policy.get("take_profit_reward_r_multiples")
    if not isinstance(horizons, list) or not horizons or not isinstance(stop_grid, list) or not stop_grid or not isinstance(reward_grid, list) or not reward_grid:
        raise MultiPositionAdapterError("policy parameter grids must be non-empty arrays")
    if any(isinstance(h, bool) or not isinstance(h, int) or not 10 <= h <= 60 for h in horizons):
        raise MultiPositionAdapterError("holding_seconds must contain only integers from 10 through 60")
    if any(_positive(v, "stop_volatility_multiplier") <= 0 for v in stop_grid):
        raise MultiPositionAdapterError("stop multiplier grid is invalid")
    if any(_positive(v, "take_profit_reward_r_multiple") <= 0 for v in reward_grid):
        raise MultiPositionAdapterError("reward multiple grid is invalid")

    output: list[dict[str, Any]] = []
    skipped_short_horizon = 0
    skipped_incomplete_scale = 0
    for event in candidates["events"]:
        if not isinstance(event, dict):
            raise MultiPositionAdapterError("candidate event must be an object")
        horizon = event.get("horizon_seconds")
        if horizon not in horizons:
            skipped_short_horizon += 1
            continue
        index = event.get("signal_window_index")
        if isinstance(index, bool) or not isinstance(index, int) or index <= 0 or index >= len(rows):
            skipped_incomplete_scale += 1
            continue
        params = event.get("parameters", {})
        lookback = params.get("lookback_seconds")
        if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback <= 0 or lookback % 5:
            raise MultiPositionAdapterError("candidate event has invalid registered lookback_seconds")
        n = lookback // 5
        if index < n:
            skipped_incomplete_scale += 1
            continue
        prior = rows[index - n:index]
        stamps = [row.get("window_start_utc") for row in prior]
        if any(not isinstance(stamp, str) for stamp in stamps):
            skipped_incomplete_scale += 1
            continue
        # The feature generator guarantees UTC-aligned windows; this explicit
        # contiguity check prevents a volatility scale spanning a data gap.
        from datetime import datetime
        try:
            millis = [int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000) for x in stamps]
        except ValueError as exc:
            raise MultiPositionAdapterError("prior feature timestamp is invalid") from exc
        if any(millis[i] - millis[i-1] != 5000 for i in range(1, len(millis))):
            skipped_incomplete_scale += 1
            continue
        vol_values = [row.get("realized_volatility_bps") for row in prior]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or v < 0 for v in vol_values):
            skipped_incomplete_scale += 1
            continue
        scale_bps = math.sqrt(sum(float(v) ** 2 for v in vol_values))
        mid = _positive(rows[index].get("mid_close"), "signal mid_close")
        if not math.isfinite(scale_bps) or scale_bps <= 0:
            skipped_incomplete_scale += 1
            continue
        base_volatility_price = mid * scale_bps / 10000.0
        for stop_multiple, reward_r in itertools.product(stop_grid, reward_grid):
            stop_distance = _tick_ceil(
                max(base_volatility_price * float(stop_multiple), spec["minimum_stop_distance"]),
                spec["tick_size"],
            )
            target_distance = _tick_ceil(
                max(stop_distance * float(reward_r), spec["minimum_stop_distance"]),
                spec["tick_size"],
            )
            config_id = f"sl{float(stop_multiple):g}_rr{float(reward_r):g}_h{horizon}"
            output.append({
                "signal_id": f"{event['signal_id']}:{config_id}",
                "candidate_id": event.get("candidate_id"),
                "portfolio_config_id": config_id,
                "signal_window_end_msc": event["signal_window_end_msc"],
                "direction": event["direction"],
                "hold_seconds": horizon,
                "stop_distance_price": stop_distance,
                "take_profit_distance_price": target_distance,
                "volatility_scale_bps": round(scale_bps, 8),
                "stop_volatility_multiple": float(stop_multiple),
                "take_profit_reward_r_multiple": float(reward_r),
                "effective_reward_r_multiple": round(target_distance / stop_distance, 8),
                "event_origin": "ADAPTED_RESEARCH_SIGNAL_NOT_TRADE",
                "execution_authorized": False,
            })
    output.sort(key=lambda item: (item["signal_window_end_msc"], item["candidate_id"] or "", item["signal_id"]))
    policy_hash = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "status": "PASS",
        "research_only": True,
        "schema": "VELTRIX_XAUUSD_MULTI_POSITION_EVENTS_V1",
        "source_sha256": features["source_sha256"],
        "policy_sha256": policy_hash,
        "data_role": candidates.get("data_role", "UNCLASSIFIED_NOT_HOLDOUT"),
        "final_holdout_eligible": False,
        "event_count": len(output),
        "skipped_legacy_short_horizon_events": skipped_short_horizon,
        "skipped_incomplete_volatility_events": skipped_incomplete_scale,
        "events": output,
        "limitations": [
            "Past-only volatility determines distance scale; multiplier grids are research hypotheses, not selected settings.",
            "Five-second legacy holding events are excluded; retained horizons are 10-60 seconds.",
            "No candidate performance, PnL, or actual fill is asserted.",
            "Commission and execution quality remain unverified.",
            "No broker orders are sent.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--candidate-events", type=Path, required=True)
    parser.add_argument("--broker-spec", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("research/xauusd_multi_position_policy_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        features = json.loads(args.features.read_text(encoding="utf-8"))
        candidates = json.loads(args.candidate_events.read_text(encoding="utf-8"))
        broker = json.loads(args.broker_spec.read_text(encoding="utf-8"))
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        result = build_multi_position_events(features, candidates, broker, policy)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, MultiPositionAdapterError) as exc:
        parser.exit(2, f"MULTI-POSITION EVENT ADAPTER FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
