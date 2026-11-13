"""Deterministic, offline XAUUSD tick replay for preregistered research events.

The replay measures observed bid/ask outcomes. It does not simulate broker
orders, create trade signals, or enable execution.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.mt5_tick_market_profile import ProfileError, profile_dataset
from tools.mt5_xauusd_feature_research import build_features

REPLAY_SCHEMA = "VELTRIX_XAUUSD_TICK_REPLAY_V1"
HYPOTHESES = ("H1_TREND_CONTINUATION", "H2_RANGE_REVERSION", "H3_ACTIVITY_CONFIRMED_EXPANSION")
METRICS = ("trend_efficiency", "ticks_per_second", "realized_volatility_bps", "return_bps")


class ReplayError(ValueError):
    """Raised when replay inputs or frozen configuration are invalid."""


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _utc_ms(value: str) -> int:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
        raise ReplayError("feature window timestamp must be UTC")
    return int(stamp.timestamp() * 1000)


def _validate_registry(registry: dict[str, Any], config: dict[str, Any]) -> tuple[list[int], int, int, int]:
    if registry.get("instrument") != "XAUUSD" or registry.get("status") != "PREREGISTERED_UNTESTED":
        raise ReplayError("registry must be the preregistered XAUUSD hypothesis registry")
    if registry.get("evaluation_policy", {}).get("trade_execution") is not False:
        raise ReplayError("registry must explicitly prohibit trade execution")
    if config.get("schema") != "VELTRIX_XAUUSD_REPLAY_CONFIG_V1":
        raise ReplayError("unsupported replay config schema")
    if config.get("trade_execution") is not False or config.get("forward_fill") is not False:
        raise ReplayError("replay config must disable execution and forward filling")
    if config.get("quote_tolerance_frozen") is not True:
        raise ReplayError("maximum quote delay must be frozen before replay")
    horizons = config.get("holding_horizons_seconds")
    if horizons != registry.get("holding_horizons_seconds") or not isinstance(horizons, list):
        raise ReplayError("replay horizons must match the preregistered registry")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 5 <= x <= 60 for x in horizons):
        raise ReplayError("holding horizons must be integer seconds between 5 and 60")
    if horizons != sorted(set(horizons)):
        raise ReplayError("holding horizons must be unique and ascending")
    lookback = config.get("lookback_populated_windows")
    minimum = config.get("minimum_valid_prior_observations")
    delay = config.get("max_quote_delay_ms")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or not 1 <= lookback <= 300:
        raise ReplayError("lookback_populated_windows must be 1..300")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= lookback:
        raise ReplayError("minimum_valid_prior_observations must be 1..lookback")
    if isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 5000:
        raise ReplayError("max_quote_delay_ms must be 0..5000")
    for key in ("commission_bps", "slippage_bps"):
        value = config.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            raise ReplayError(f"{key} must be null or a finite non-negative number")
    registry_ids = {item.get("id") for item in registry.get("hypotheses", []) if isinstance(item, dict)}
    if not set(HYPOTHESES).issubset(registry_ids):
        raise ReplayError("registry is missing a supported hypothesis")
    return horizons, lookback, minimum, delay


def _load_ticks(csv_path: str | Path) -> tuple[list[int], list[tuple[float, float]]]:
    stamps: list[int] = []
    quotes: list[tuple[float, float]] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stamps.append(int(row["time_msc"]))
            quotes.append((float(row["bid"]), float(row["ask"])))
    if not stamps:
        raise ReplayError("tick dataset is empty")
    return stamps, quotes


def replay_dataset(
    csv_path: str | Path,
    manifest_path: str | Path,
    registry: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    horizons, lookback, minimum, max_delay = _validate_registry(registry, config)
    profile = profile_dataset(csv_path, manifest_path)
    features = build_features(csv_path, manifest_path, window_seconds=int(registry["feature_window_seconds"]))
    if features["source_sha256"] != profile["sha256"] or features["source_records"] != profile["records"]:
        raise ReplayError("feature source provenance does not match the verified tick dataset")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    point = float(manifest["instrument_specs"]["XAUUSD"]["point"])
    stamps, quotes = _load_ticks(csv_path)
    windows = features["features"]
    events: list[dict[str, Any]] = []
    warmup_windows = 0

    for index, row in enumerate(windows):
        prior_rows = windows[max(0, index - lookback):index]
        prior = {
            "trend_efficiency": [float(x["trend_efficiency"]) for x in prior_rows if x.get("trend_efficiency") is not None],
            "ticks_per_second": [float(x["ticks_per_second"]) for x in prior_rows if x.get("ticks_per_second") is not None],
            "realized_volatility_bps": [float(x["realized_volatility_bps"]) for x in prior_rows if x.get("realized_volatility_bps") is not None],
            "abs_return_bps": [abs(float(x["return_bps"])) for x in prior_rows if x.get("return_bps") is not None],
        }
        if any(len(values) < minimum for values in prior.values()):
            warmup_windows += 1
            continue
        if any(row.get(metric) is None for metric in METRICS) or row.get("return_bps") is None:
            continue
        thresholds = {
            "trend_efficiency_p25": _percentile(prior["trend_efficiency"], 0.25),
            "trend_efficiency_p75": _percentile(prior["trend_efficiency"], 0.75),
            "ticks_per_second_p75": _percentile(prior["ticks_per_second"], 0.75),
            "realized_volatility_bps_p75": _percentile(prior["realized_volatility_bps"], 0.75),
            "abs_return_bps_p75": _percentile(prior["abs_return_bps"], 0.75),
        }
        ret = float(row["return_bps"])
        abs_ret = abs(ret)
        if abs_ret <= 0:
            continue
        triggers: list[tuple[str, int]] = []
        if float(row["trend_efficiency"]) >= thresholds["trend_efficiency_p75"] and abs_ret >= thresholds["abs_return_bps_p75"]:
            triggers.append(("H1_TREND_CONTINUATION", 1 if ret > 0 else -1))
        if float(row["trend_efficiency"]) <= thresholds["trend_efficiency_p25"] and abs_ret >= thresholds["abs_return_bps_p75"]:
            triggers.append(("H2_RANGE_REVERSION", -1 if ret > 0 else 1))
        if float(row["ticks_per_second"]) >= thresholds["ticks_per_second_p75"] and float(row["realized_volatility_bps"]) >= thresholds["realized_volatility_bps_p75"]:
            triggers.append(("H3_ACTIVITY_CONFIRMED_EXPANSION", 1 if ret > 0 else -1))
        if not triggers:
            triggers.append(("BASELINE_NONZERO_RETURN", 1 if ret > 0 else -1))

        decision_ms = _utc_ms(row["window_start_utc"]) + features["window_seconds"] * 1000
        entry_index = bisect.bisect_left(stamps, decision_ms)
        entry_available = entry_index < len(stamps) and stamps[entry_index] - decision_ms <= max_delay
        for hypothesis, direction in triggers:
            event_id = f"{profile['sha256'][:12]}-{index:05d}-{hypothesis}"
            event: dict[str, Any] = {
                "event_id": event_id,
                "hypothesis": hypothesis,
                "decision_time_utc": datetime.fromtimestamp(decision_ms / 1000, timezone.utc).isoformat(),
                "feature_window_start_utc": row["window_start_utc"],
                "direction": "LONG" if direction > 0 else "SHORT",
                "threshold_history_count": min(len(values) for values in prior.values()),
                "threshold_history_end_utc": prior_rows[-1]["window_start_utc"],
                "thresholds": {key: round(value, 8) for key, value in thresholds.items()},
                "entry_quote_status": "OBSERVED" if entry_available else "UNAVAILABLE",
                "entry_quote_delay_ms": stamps[entry_index] - decision_ms if entry_available else None,
                "entry_spread_points": round((quotes[entry_index][1] - quotes[entry_index][0]) / point, 6) if entry_available else None,
                "outcomes": [],
            }
            if entry_available:
                entry_bid, entry_ask = quotes[entry_index]
                entry_price = entry_ask if direction > 0 else entry_bid
                stop_reference = float(row["mid_low"] if direction > 0 else row["mid_high"])
                for horizon in horizons:
                    target_ms = decision_ms + horizon * 1000
                    exit_index = bisect.bisect_left(stamps, target_ms)
                    target_available = exit_index < len(stamps) and stamps[exit_index] - target_ms <= max_delay
                    outcome: dict[str, Any] = {
                        "horizon_seconds": horizon,
                        "target_quote_status": "OBSERVED" if target_available else "UNAVAILABLE",
                        "target_quote_delay_ms": stamps[exit_index] - target_ms if target_available else None,
                        "bid_ask_adjusted_gross_return_bps": None,
                        "net_return_bps": None,
                        "favourable_excursion_bps": None,
                        "adverse_excursion_bps": None,
                        "invalidation_touched": None,
                        "invalidation_first_touch_delay_ms": None,
                        "invalidation_return_bps": None,
                    }
                    if target_available:
                        exit_bid, exit_ask = quotes[exit_index]
                        exit_price = exit_bid if direction > 0 else exit_ask
                        gross = ((exit_price - entry_price) / entry_price * 10000) if direction > 0 else ((entry_price - exit_price) / entry_price * 10000)
                        commission = config.get("commission_bps")
                        slippage = config.get("slippage_bps")
                        outcome["bid_ask_adjusted_gross_return_bps"] = round(gross, 8)
                        outcome["net_return_bps"] = round(gross - commission - slippage, 8) if commission is not None and slippage is not None else None
                        path_returns = []
                        invalidation_index = None
                        for tick_index in range(entry_index, exit_index + 1):
                            bid, ask = quotes[tick_index]
                            mid = (bid + ask) / 2
                            side_return = ((bid - entry_price) / entry_price * 10000) if direction > 0 else ((entry_price - ask) / entry_price * 10000)
                            path_returns.append(side_return)
                            touched = mid < stop_reference if direction > 0 else mid > stop_reference
                            if touched and invalidation_index is None:
                                invalidation_index = tick_index
                        if path_returns:
                            outcome["favourable_excursion_bps"] = round(max(path_returns), 8)
                            outcome["adverse_excursion_bps"] = round(min(path_returns), 8)
                        outcome["invalidation_touched"] = invalidation_index is not None
                        if invalidation_index is not None:
                            bid, ask = quotes[invalidation_index]
                            stop_exit = bid if direction > 0 else ask
                            stop_gross = ((stop_exit - entry_price) / entry_price * 10000) if direction > 0 else ((entry_price - stop_exit) / entry_price * 10000)
                            outcome["invalidation_first_touch_delay_ms"] = stamps[invalidation_index] - decision_ms
                            outcome["invalidation_return_bps"] = round(stop_gross, 8)
                    event["outcomes"].append(outcome)
            else:
                for horizon in horizons:
                    event["outcomes"].append({
                        "horizon_seconds": horizon, "target_quote_status": "ENTRY_QUOTE_UNAVAILABLE",
                        "target_quote_delay_ms": None, "bid_ask_adjusted_gross_return_bps": None,
                        "net_return_bps": None, "favourable_excursion_bps": None,
                        "adverse_excursion_bps": None, "invalidation_touched": None,
                        "invalidation_first_touch_delay_ms": None, "invalidation_return_bps": None,
                    })
            events.append(event)

    summary: dict[str, Any] = {}
    categories = list(HYPOTHESES) + ["BASELINE_NONZERO_RETURN"]
    for category in categories:
        category_events = [event for event in events if event["hypothesis"] == category]
        summary[category] = {}
        for horizon in horizons:
            outcomes = [item for event in category_events for item in event["outcomes"] if item["horizon_seconds"] == horizon]
            observed = [float(item["bid_ask_adjusted_gross_return_bps"]) for item in outcomes if item["bid_ask_adjusted_gross_return_bps"] is not None]
            net_observed = [
                float(item["net_return_bps"])
                for item in outcomes
                if item["net_return_bps"] is not None
            ]
            summary[category][str(horizon)] = {
                "events": len(category_events),
                "observed_outcomes": len(observed),
                "unavailable_outcomes": len(outcomes) - len(observed),
                "mean_bid_ask_adjusted_gross_return_bps": round(sum(observed) / len(observed), 8) if observed else None,
                "median_bid_ask_adjusted_gross_return_bps": round(_percentile(observed, 0.5), 8) if observed else None,
                "positive_outcome_rate": round(sum(value > 0 for value in observed) / len(observed), 8) if observed else None,
                "net_observed_outcomes": len(net_observed),
                "mean_net_return_bps": round(sum(net_observed) / len(net_observed), 8) if net_observed else None,
            }

    return {
        "status": "PASS",
        "research_only": True,
        "replay_schema": REPLAY_SCHEMA,
        "canonical_symbol": "XAUUSD",
        "source_sha256": profile["sha256"],
        "source_records": profile["records"],
        "feature_window_seconds": features["window_seconds"],
        "lookback_populated_windows": lookback,
        "minimum_valid_prior_observations": minimum,
        "max_quote_delay_ms": max_delay,
        "holding_horizons_seconds": horizons,
        "warmup_windows": warmup_windows,
        "event_count": len(events),
        "events_by_hypothesis": {category: sum(event["hypothesis"] == category for event in events) for category in categories},
        "summary": summary,
        "events": events,
        "commission_bps": config.get("commission_bps"),
        "slippage_bps": config.get("slippage_bps"),
        "trade_execution": False,
        "limitations": [
            "Offline event replay only; no broker orders, fills, or execution simulation.",
            "Bid/ask-adjusted gross returns include observed spread but exclude commission and slippage unless separately configured.",
            "No forward fill; entry and target quotes outside the frozen delay tolerance are unavailable.",
            "Invalidation touches are observed quote crossings, not guaranteed stop fills.",
            "Small historical samples and event overlap do not establish profitability or out-of-sample predictive power.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_hypotheses.json"))
    parser.add_argument("--config", type=Path, default=Path("research/xauusd_replay_config.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        config = json.loads(args.config.read_text(encoding="utf-8"))
        result = replay_dataset(args.csv, args.manifest, registry, config)
    except (OSError, json.JSONDecodeError, ProfileError, ReplayError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"XAUUSD REPLAY FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
