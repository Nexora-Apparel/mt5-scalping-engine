"""Build causal, descriptive XAUUSD features from a verified MT5 tick dataset.
This module does not create trade signals, labels, orders, or profitability claims.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.mt5_tick_market_profile import HEADER, ProfileError, percentile, profile_dataset

def _finite(value: str, field: str, line: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"line {line}: invalid {field}") from exc
    if not math.isfinite(parsed):
        raise ProfileError(f"line {line}: non-finite {field}")
    return parsed

def build_features(csv_path: str | Path, manifest_path: str | Path, *, window_seconds: int = 5) -> dict[str, Any]:
    """Return fixed-width, UTC-epoch-aligned feature windows."""
    if isinstance(window_seconds, bool) or not isinstance(window_seconds, int):
        raise ProfileError("window_seconds must be an integer")
    if not 1 <= window_seconds <= 300:
        raise ProfileError("window_seconds must be between 1 and 300")
    profile = profile_dataset(csv_path, manifest_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    point = float(manifest["instrument_specs"]["XAUUSD"]["point"])
    window_ms = window_seconds * 1000
    buckets: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    try:
        with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADER:
                raise ProfileError("CSV header does not match tick schema")
            for line, row in enumerate(reader, start=2):
                stamp = int(row["time_msc"])
                bid = _finite(row["bid"], "bid", line)
                ask = _finite(row["ask"], "ask", line)
                if bid <= 0 or ask < bid:
                    raise ProfileError(f"line {line}: invalid XAUUSD quote")
                bucket = (stamp // window_ms) * window_ms
                buckets[bucket].append((stamp, (bid + ask) / 2, (ask - bid) / point))
    except OSError as exc:
        raise ProfileError(f"unable to read tick CSV: {exc}") from exc
    windows: list[dict[str, Any]] = []
    for start_ms in sorted(buckets):
        ticks = buckets[start_ms]
        mids = [item[1] for item in ticks]
        spreads = [item[2] for item in ticks]
        stamps = [item[0] for item in ticks]
        has_movement_observations = len(mids) >= 2
        deltas = [b - a for a, b in zip(mids, mids[1:])]
        log_returns = [math.log(b / a) for a, b in zip(mids, mids[1:]) if a > 0 and b > 0]
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        path_length = sum(abs(delta) for delta in deltas)
        net_move = mids[-1] - mids[0]
        realized_vol_bps = math.sqrt(sum(value * value for value in log_returns)) * 10000
        range_bps = (max(mids) - min(mids)) / mids[0] * 10000
        windows.append({
            "window_start_utc": datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat(),
            "window_seconds": window_seconds,
            "tick_count": len(ticks),
            "observed_span_ms": stamps[-1] - stamps[0],
            "ticks_per_second": round(len(ticks) / ((stamps[-1] - stamps[0]) / 1000), 6) if stamps[-1] > stamps[0] else None,
            "mid_open": round(mids[0], 6),
            "mid_high": round(max(mids), 6),
            "mid_low": round(min(mids), 6),
            "mid_close": round(mids[-1], 6),
            "return_bps": round(math.log(mids[-1] / mids[0]) * 10000, 6) if has_movement_observations else None,
            "range_bps": round(range_bps, 6) if has_movement_observations else None,
            "realized_volatility_bps": round(realized_vol_bps, 6) if has_movement_observations else None,
            "trend_efficiency": round(abs(net_move) / path_length, 6) if path_length else (0.0 if has_movement_observations else None),
            "spread_points_median": round(percentile(spreads, 0.5), 6),
            "spread_points_p95": round(percentile(spreads, 0.95), 6),
            "spread_points_max": round(max(spreads), 6),
            "max_intertick_gap_ms": max(gaps, default=0),
            "gaps_over_1s": sum(gap > 1000 for gap in gaps),
            "mid_price_change_ratio": round(sum(a != b for a, b in zip(mids, mids[1:])) / (len(mids) - 1), 6) if has_movement_observations else None,
        })
    return {
        "status": "PASS", "research_only": True,
        "feature_schema": "VELTRIX_XAUUSD_TICK_WINDOWS_V1",
        "canonical_symbol": "XAUUSD",
        "broker_symbol": manifest["instrument_specs"]["XAUUSD"].get("broker_symbol"),
        "source_sha256": profile["sha256"], "source_records": profile["records"],
        "window_seconds": window_seconds, "window_count": len(windows), "features": windows,
        "limitations": [
            "Descriptive features only; no entry/exit signals, labels, or trade recommendations.",
            "Tick-count intensity is not traded volume; zero volume fields remain unavailable.",
            "Fixed UTC windows can be partial at dataset boundaries and are not forward-filled.",
            "Movement-derived metrics are null when a window has fewer than two ticks.",
            "A short sample cannot establish market-regime stability or strategy performance.",
        ],
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--window-seconds", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = build_features(args.csv, args.manifest, window_seconds=args.window_seconds)
    except (ProfileError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"FEATURE BUILD FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
