"""Deterministic offline XAUUSD bid/ask tick replay and quote-crossed outcome engine.

This is a research simulator only. It never sends or prepares broker orders.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.mt5_tick_market_profile import HEADER, ProfileError, profile_dataset
from tools.mt5_xauusd_strategy_registry import validate_registry


class ReplayError(ValueError):
    """Raised when tick replay inputs or event definitions are invalid."""


@dataclass(frozen=True)
class QuoteTick:
    time_msc: int
    bid: float
    ask: float


def validate_ticks(ticks: list[QuoteTick]) -> None:
    if not isinstance(ticks, list) or not ticks:
        raise ReplayError("tick stream must be a non-empty list")
    previous = None
    for index, tick in enumerate(ticks):
        if not isinstance(tick, QuoteTick):
            raise ReplayError(f"tick {index} must be a QuoteTick")
        if isinstance(tick.time_msc, bool) or not isinstance(tick.time_msc, int) or tick.time_msc <= 0:
            raise ReplayError(f"tick {index} has an invalid timestamp")
        if previous is not None and tick.time_msc < previous:
            raise ReplayError("tick timestamps must be nondecreasing")
        previous = tick.time_msc
        if not math.isfinite(tick.bid) or not math.isfinite(tick.ask) or tick.bid <= 0 or tick.ask < tick.bid:
            raise ReplayError(f"tick {index} has an invalid bid/ask quote")


def load_verified_ticks(csv_path: str | Path, manifest_path: str | Path) -> tuple[list[QuoteTick], dict[str, Any]]:
    profile = profile_dataset(csv_path, manifest_path)
    ticks: list[QuoteTick] = []
    try:
        with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADER:
                raise ReplayError("CSV header does not match the verified tick schema")
            for line, row in enumerate(reader, start=2):
                try:
                    ticks.append(QuoteTick(int(row["time_msc"]), float(row["bid"]), float(row["ask"])))
                except (TypeError, ValueError) as exc:
                    raise ReplayError(f"line {line}: invalid replay quote") from exc
    except OSError as exc:
        raise ReplayError(f"unable to read tick CSV: {exc}") from exc
    validate_ticks(ticks)
    if len(ticks) != profile["records"]:
        raise ReplayError("replay tick count differs from verified profile")
    return ticks, profile


def _validate_events(events: list[dict[str, Any]], registry: dict[str, Any]) -> None:
    candidates = {item["candidate_id"] for item in registry["candidates"]}
    seen: set[str] = set()
    if not isinstance(events, list):
        raise ReplayError("events must be a list")
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ReplayError(f"event {index} must be an object")
        signal_id = event.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id.strip() or signal_id in seen:
            raise ReplayError(f"event {index} must have a unique non-empty signal_id")
        seen.add(signal_id)
        if event.get("candidate_id") not in candidates:
            raise ReplayError(f"event {index} uses an unregistered candidate_id")
        stamp = event.get("signal_window_end_msc")
        if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp <= 0:
            raise ReplayError(f"event {index} has an invalid signal_window_end_msc")
        if event.get("direction") not in ("long", "short"):
            raise ReplayError(f"event {index} direction must be long or short")
        horizon = event.get("horizon_seconds")
        if isinstance(horizon, bool) or horizon not in registry["evaluation"]["holding_horizons_seconds"]:
            raise ReplayError(f"event {index} horizon is not preregistered")


def evaluate_event(
    ticks: list[QuoteTick],
    event: dict[str, Any],
    *,
    point_size: float,
    slippage_grid: list[int],
    entry_max_wait_ms: int = 5000,
    exit_tolerance_ms: int = 2000,
) -> dict[str, Any]:
    validate_ticks(ticks)
    if not math.isfinite(point_size) or point_size <= 0:
        raise ReplayError("point_size must be finite and positive")
    signal_end = event["signal_window_end_msc"]
    direction = event["direction"]
    horizon = event["horizon_seconds"]
    if direction not in ("long", "short"):
        raise ReplayError("direction must be long or short")
    if isinstance(signal_end, bool) or not isinstance(signal_end, int) or signal_end <= 0:
        raise ReplayError("signal_window_end_msc must be a positive integer")
    if isinstance(horizon, bool) or horizon not in (5, 15, 30, 60):
        raise ReplayError("horizon_seconds must be one of 5, 15, 30, 60")
    stamps = [tick.time_msc for tick in ticks]
    entry_index = bisect.bisect_right(stamps, signal_end)
    base = {
        "signal_id": event["signal_id"],
        "candidate_id": event["candidate_id"],
        "direction": direction,
        "horizon_seconds": horizon,
        "signal_window_end_msc": signal_end,
        "spread_included_once": True,
        "execution_sent": False,
        "actual_fill_claimed": False,
    }
    if entry_index >= len(ticks) or ticks[entry_index].time_msc - signal_end > entry_max_wait_ms:
        return {**base, "status": "ENTRY_QUOTE_TIMEOUT"}
    entry = ticks[entry_index]
    target_exit = entry.time_msc + horizon * 1000
    exit_index = bisect.bisect_left(stamps, target_exit)
    if exit_index >= len(ticks) or ticks[exit_index].time_msc - target_exit > exit_tolerance_ms:
        return {
            **base,
            "status": "EXIT_QUOTE_TIMEOUT",
            "entry_time_msc": entry.time_msc,
            "entry_delay_ms": entry.time_msc - signal_end,
            "target_exit_time_msc": target_exit,
        }
    exit_tick = ticks[exit_index]
    if direction == "long":
        entry_price, exit_price = entry.ask, exit_tick.bid
    else:
        entry_price, exit_price = entry.bid, exit_tick.ask
    gross = exit_price - entry_price
    gross_bps = gross / entry_price * 10000
    sensitivity = []
    for slip_points in slippage_grid:
        if isinstance(slip_points, bool) or not isinstance(slip_points, int) or slip_points < 0:
            raise ReplayError("slippage grid must contain nonnegative integer points per side")
        slippage_price = 2 * slip_points * point_size
        before_commission = gross - slippage_price
        sensitivity.append({
            "slippage_points_per_side": slip_points,
            "slippage_price_units_round_trip": round(slippage_price, 9),
            "pnl_before_commission_price_units": round(before_commission, 9),
            "return_before_commission_bps": round(before_commission / entry_price * 10000, 8),
            "net_after_commission": None,
        })
    return {
        **base,
        "status": "OUTCOME_AVAILABLE",
        "entry_time_msc": entry.time_msc,
        "entry_delay_ms": entry.time_msc - signal_end,
        "target_exit_time_msc": target_exit,
        "exit_time_msc": exit_tick.time_msc,
        "exit_delay_ms": exit_tick.time_msc - target_exit,
        "entry_bid": entry.bid,
        "entry_ask": entry.ask,
        "exit_bid": exit_tick.bid,
        "exit_ask": exit_tick.ask,
        "entry_spread_points": round((entry.ask - entry.bid) / point_size, 6),
        "exit_spread_points": round((exit_tick.ask - exit_tick.bid) / point_size, 6),
        "entry_executable_price": entry_price,
        "exit_executable_price": exit_price,
        "gross_pnl_price_units": round(gross, 9),
        "gross_return_bps": round(gross_bps, 8),
        "slippage_sensitivity": sensitivity,
        "commission_status": "UNVERIFIED_REQUIRED_INPUT",
        "net_after_commission": None,
    }


def replay_events(
    ticks: list[QuoteTick],
    events: list[dict[str, Any]],
    manifest: dict[str, Any],
    registry: dict[str, Any],
    *,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_ticks(ticks)
    registry_result = validate_registry(registry)
    _validate_events(events, registry)
    if manifest.get("account_mode") != "DEMO" or manifest.get("trading_enabled") is not False or manifest.get("dll_imports_enabled") is not False:
        raise ReplayError("source manifest must prove DEMO mode with trading and DLL imports disabled")
    if set(manifest.get("instrument_specs", {})) != {"XAUUSD"}:
        raise ReplayError("source manifest must contain XAUUSD only")
    spec = manifest["instrument_specs"]["XAUUSD"]
    if spec.get("currency_base") != "XAU" or spec.get("currency_profit") != "USD":
        raise ReplayError("source contract metadata is not verified XAUUSD")
    point = float(spec.get("point", 0))
    if not math.isfinite(point) or point <= 0:
        raise ReplayError("source XAUUSD point size is invalid")
    slippage_grid = registry["evaluation"]["additional_costs"]["slippage_sensitivity_points_per_side"]
    outcomes = [
        evaluate_event(
            ticks,
            event,
            point_size=point,
            slippage_grid=slippage_grid,
            entry_max_wait_ms=registry["evaluation"]["entry_max_wait_seconds"] * 1000,
            exit_tolerance_ms=2000,
        )
        for event in events
    ]
    profile = source_profile or {}
    return {
        "status": "PASS",
        "research_only": True,
        "replay_schema": "VELTRIX_XAUUSD_QUOTE_REPLAY_V1",
        "canonical_symbol": "XAUUSD",
        "broker_symbol": spec.get("broker_symbol"),
        "account_mode": "DEMO",
        "source_sha256": profile.get("sha256", manifest.get("sha256")),
        "source_records": len(ticks),
        "source_span_start_msc": ticks[0].time_msc,
        "source_span_end_msc": ticks[-1].time_msc,
        "point_size": point,
        "registry_sha256": registry_result["registry_sha256"],
        "commission_status": registry_result["commission_status"],
        "event_count": len(events),
        "outcome_available_count": sum(item["status"] == "OUTCOME_AVAILABLE" for item in outcomes),
        "entry_timeout_count": sum(item["status"] == "ENTRY_QUOTE_TIMEOUT" for item in outcomes),
        "exit_timeout_count": sum(item["status"] == "EXIT_QUOTE_TIMEOUT" for item in outcomes),
        "outcomes": outcomes,
        "limitations": [
            "Deterministic historical quote replay only; no broker order or actual fill is created.",
            "Executable bid/ask crossing includes the observed spread exactly once.",
            "Commission remains unverified; net-after-commission values are null.",
            "Slippage values are sensitivity assumptions, not measured execution slippage.",
            "Theoretical quote outcomes do not establish fill probability, market impact, or profitability.",
            "No signal generation is performed by this replay module; events must come from a separately validated candidate engine.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        ticks, profile = load_verified_ticks(args.csv, args.manifest)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        events_payload = json.loads(args.events.read_text(encoding="utf-8"))
        events = events_payload.get("events") if isinstance(events_payload, dict) else None
        result = replay_events(ticks, events, manifest, registry, source_profile=profile)
    except (OSError, json.JSONDecodeError, ProfileError, ReplayError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"REPLAY FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
