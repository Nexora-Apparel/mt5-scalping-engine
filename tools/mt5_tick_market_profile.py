"""Offline market-data profile for a previously collected Veltrix MT5 tick CSV.

This tool never connects to MT5 and never places or manages orders. It verifies
the dataset against its manifest and reports descriptive microstructure metrics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HEADER = [
    "schema_version", "source_id", "canonical_symbol", "broker_symbol",
    "time_msc", "time_utc", "bid", "ask", "last", "volume",
    "volume_real", "flags",
]
EXPECTED = ("XAUUSD", "XAGUSD")


class ProfileError(ValueError):
    pass


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def profile_dataset(csv_path: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    csv_file, manifest_file = Path(csv_path), Path(manifest_path)
    if not csv_file.is_file() or not manifest_file.is_file():
        raise ProfileError("CSV dataset and manifest must both exist")
    raw = csv_file.read_bytes()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError("manifest is not valid UTF-8 JSON") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.get("sha256"):
        raise ProfileError("CSV SHA-256 does not match manifest")
    if manifest.get("account_mode") != "DEMO":
        raise ProfileError("manifest account mode is not DEMO")
    if manifest.get("trading_enabled") is not False or manifest.get("dll_imports_enabled") is not False:
        raise ProfileError("manifest does not prove trading and DLL imports are disabled")

    streams: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    seen: set[tuple[Any, ...]] = set()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProfileError("CSV is not valid UTF-8") from exc
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames != HEADER:
        raise ProfileError("CSV header does not match tick schema")
    records = 0
    for line, row in enumerate(reader, start=2):
        if None in row or any(row.get(key) in (None, "") for key in HEADER):
            raise ProfileError(f"line {line}: missing or extra field")
        if row["schema_version"] != "1" or row["canonical_symbol"] not in EXPECTED:
            raise ProfileError(f"line {line}: unsupported schema or symbol")
        try:
            stamp = int(row["time_msc"])
            bid, ask = float(row["bid"]), float(row["ask"])
            last = float(row["last"])
            volume, volume_real = float(row["volume"]), float(row["volume_real"])
            int(row["flags"])
        except (TypeError, ValueError) as exc:
            raise ProfileError(f"line {line}: invalid numeric field") from exc
        if stamp <= 0 or not all(math.isfinite(x) for x in (bid, ask, last, volume, volume_real)):
            raise ProfileError(f"line {line}: non-finite or invalid numeric value")
        if bid <= 0 or ask < bid or volume < 0 or volume_real < 0:
            raise ProfileError(f"line {line}: invalid quote or volume")
        expected_utc = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).isoformat()
        if row["time_utc"] != expected_utc:
            raise ProfileError(f"line {line}: UTC timestamp mismatch")
        key = tuple(row[k] for k in HEADER)
        if key in seen:
            raise ProfileError(f"line {line}: duplicate tick row")
        seen.add(key)
        streams[row["canonical_symbol"]].append((stamp, bid, ask))
        records += 1

    if records != manifest.get("records"):
        raise ProfileError("CSV record count does not match manifest")
    if set(streams) != set(EXPECTED):
        raise ProfileError("dataset must contain both XAUUSD and XAGUSD")
    output: dict[str, Any] = {}
    overall_review = False
    for symbol in EXPECTED:
        ticks = streams[symbol]
        stamps = [x[0] for x in ticks]
        if any(a > b for a, b in zip(stamps, stamps[1:])):
            raise ProfileError(f"{symbol}: timestamps moved backwards")
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        spreads = [ask - bid for _, bid, ask in ticks]
        spec = manifest.get("instrument_specs", {}).get(symbol, {})
        point = float(spec.get("point", 0))
        if not math.isfinite(point) or point <= 0:
            raise ProfileError(f"{symbol}: missing or invalid instrument point size")
        spread_points = [value / point for value in spreads]
        span_seconds = (stamps[-1] - stamps[0]) / 1000 if len(stamps) > 1 else 0.0
        gaps_over_5s = sum(gap > 5000 for gap in gaps)
        status = "REVIEW" if gaps_over_5s else "PASS"
        overall_review = overall_review or status == "REVIEW"
        output[symbol] = {
            "status": status,
            "records": len(ticks),
            "span_seconds": round(span_seconds, 3),
            "ticks_per_second": round(len(ticks) / span_seconds, 4) if span_seconds else None,
            "max_intertick_gap_ms": max(gaps, default=0),
            "gaps_over_1s": sum(gap > 1000 for gap in gaps),
            "gaps_over_5s": gaps_over_5s,
            "gaps_over_10s": sum(gap > 10000 for gap in gaps),
            "intertick_gap_ms_p50": percentile(gaps, 0.50),
            "intertick_gap_ms_p95": percentile(gaps, 0.95),
            "intertick_gap_ms_p99": percentile(gaps, 0.99),
            "spread_points_min": round(min(spread_points), 6),
            "spread_points_median": round(percentile(spread_points, 0.50), 6),
            "spread_points_p95": round(percentile(spread_points, 0.95), 6),
            "spread_points_max": round(max(spread_points), 6),
            "point_size": point,
            "broker_symbol": spec.get("broker_symbol"),
        }
    return {
        "status": "REVIEW" if overall_review else "PASS",
        "profile_type": "OFFLINE_DESCRIPTIVE_ONLY",
        "records": records,
        "sha256": digest,
        "account_mode": "DEMO",
        "trading_enabled": False,
        "dll_imports_enabled": False,
        "symbols": output,
        "limitations": [
            "Descriptive tick profile only; not a trading signal or execution-readiness certification.",
            "Observed tick gaps can reflect market inactivity, broker feed behavior, or collection transport.",
            "No profitability, slippage, fill quality, or future quote availability is inferred.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = profile_dataset(args.csv, args.manifest)
    except (ProfileError, OSError) as exc:
        parser.exit(2, f"PROFILE FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
