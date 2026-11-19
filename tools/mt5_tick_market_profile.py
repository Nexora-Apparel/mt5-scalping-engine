"""Offline XAUUSD-only market-data profile for a previously collected MT5 tick CSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HEADER = ["schema_version", "source_id", "canonical_symbol", "broker_symbol",
          "time_msc", "time_utc", "bid", "ask", "last", "volume", "volume_real", "flags"]
EXPECTED = ("XAUUSD",)


class ProfileError(ValueError):
    pass


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def profile_dataset(
    csv_path: str | Path, manifest_path: str | Path, *,
    allow_legacy_historical: bool = False,
) -> dict[str, Any]:
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
    if manifest.get("status") != "PASS":
        raise ProfileError("collector manifest overall status is not PASS")
    if manifest.get("account_mode") != "DEMO":
        raise ProfileError("manifest account mode is not DEMO")
    if manifest.get("trading_enabled") is not False:
        raise ProfileError("manifest does not prove trading is disabled")
    legacy_historical = (
        allow_legacy_historical
        and manifest.get("schema") == "VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V2"
    )
    if not legacy_historical and manifest.get("dll_imports_enabled") is not False:
        raise ProfileError("manifest does not prove DLL imports are disabled")
    if legacy_historical:
        if (
            manifest.get("canonical_symbol") != "XAUUSD"
            or not isinstance(manifest.get("broker_symbol"), str)
            or not manifest.get("broker_symbol")
            or manifest.get("source") != "authenticated Exness MT5 DEMO terminal historical tick API"
            or not manifest.get("source_ref")
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", "")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("dispatcher_commit", "")))
            or not re.fullmatch(r"[A-Fa-f0-9]{40}", str(manifest.get("installer_signer_thumbprint", "")))
        ):
            raise ProfileError("legacy historical manifest lacks required source/symbol provenance")
        try:
            start = datetime.fromisoformat(str(manifest["requested_start_utc"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(manifest["requested_end_utc"]).replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end < start:
                raise ValueError("invalid interval bounds")
            legacy_start_ms = int(start.astimezone(timezone.utc).timestamp() * 1000)
            legacy_end_ms = int(end.astimezone(timezone.utc).timestamp() * 1000)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ProfileError("legacy historical manifest interval bounds are invalid") from exc
        try:
            legacy_point = float(manifest.get("instrument_point", 0))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ProfileError("legacy historical point size is invalid") from exc
        if not math.isfinite(legacy_point) or legacy_point <= 0:
            raise ProfileError("legacy historical point size is invalid")
    streams: dict[str, list[tuple[int, float, float, float, float]]] = defaultdict(list)
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
            raise ProfileError(f"line {line}: unsupported schema or instrument; XAUUSD only")
        if legacy_historical and (
            row["broker_symbol"] != manifest["broker_symbol"]
            or not legacy_start_ms <= int(row["time_msc"]) <= legacy_end_ms
        ):
            raise ProfileError(f"line {line}: legacy source symbol or requested interval mismatch")
        try:
            stamp = int(row["time_msc"])
            bid, ask, last = float(row["bid"]), float(row["ask"]), float(row["last"])
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
        streams[row["canonical_symbol"]].append((stamp, bid, ask, last, volume_real))
        records += 1
    if records != manifest.get("records"):
        raise ProfileError("CSV record count does not match manifest")
    if set(streams) != {"XAUUSD"}:
        raise ProfileError("dataset must contain XAUUSD only")
    output: dict[str, Any] = {}
    overall_review = False
    for symbol in EXPECTED:
        ticks = streams[symbol]
        stamps = [x[0] for x in ticks]
        if any(a > b for a, b in zip(stamps, stamps[1:])):
            raise ProfileError(f"{symbol}: timestamps moved backwards")
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        spreads = [ask - bid for _, bid, ask, _, _ in ticks]
        pairs = [(bid, ask) for _, bid, ask, _, _ in ticks]
        changes = sum(a != b for a, b in zip(pairs, pairs[1:]))
        spec = manifest.get("instrument_specs", {}).get(symbol, {})
        if legacy_historical:
            spec = {
                "point": legacy_point,
                "broker_symbol": manifest.get("broker_symbol"),
            }
        point = float(spec.get("point", 0))
        if not math.isfinite(point) or point <= 0:
            raise ProfileError(f"{symbol}: missing or invalid instrument point size")
        spread_points = [value / point for value in spreads]
        zero_last = sum(last == 0 for _, _, _, last, _ in ticks)
        zero_volume = sum(volume_real == 0 for _, _, _, _, volume_real in ticks)
        span = (stamps[-1] - stamps[0]) / 1000 if len(stamps) > 1 else 0.0
        gaps5 = sum(gap > 5000 for gap in gaps)
        status = "REVIEW" if gaps5 else "PASS"
        overall_review = overall_review or status == "REVIEW"
        output[symbol] = {
            "status": status, "records": len(ticks), "span_seconds": round(span, 3),
            "ticks_per_second": round(len(ticks) / span, 4) if span else None,
            "unique_bid_ask_pairs": len(set(pairs)), "quote_change_count": changes,
            "unique_spread_values": len({round(value, 6) for value in spread_points}),
            "zero_last_records": zero_last, "zero_last_pct": round(100 * zero_last / len(ticks), 3),
            "zero_volume_real_records": zero_volume,
            "zero_volume_real_pct": round(100 * zero_volume / len(ticks), 3),
            "max_intertick_gap_ms": max(gaps, default=0),
            "gaps_over_1s": sum(gap > 1000 for gap in gaps), "gaps_over_5s": gaps5,
            "gaps_over_10s": sum(gap > 10000 for gap in gaps),
            "intertick_gap_ms_p50": percentile(gaps, 0.50),
            "intertick_gap_ms_p95": percentile(gaps, 0.95),
            "intertick_gap_ms_p99": percentile(gaps, 0.99),
            "spread_points_min": round(min(spread_points), 6),
            "spread_points_median": round(percentile(spread_points, 0.50), 6),
            "spread_points_p95": round(percentile(spread_points, 0.95), 6),
            "spread_points_max": round(max(spread_points), 6),
            "point_size": point, "broker_symbol": spec.get("broker_symbol"),
        }
    return {
        "status": "REVIEW" if overall_review else "PASS",
        "profile_type": "OFFLINE_DESCRIPTIVE_ONLY", "records": records, "sha256": digest,
        "account_mode": "DEMO", "trading_enabled": False,
        "dll_imports_enabled": manifest.get("dll_imports_enabled"),
        "dll_imports_runtime_verified": not legacy_historical,
        "instrument_metadata_status": (
            "POINT_ONLY_CURRENCIES_UNVERIFIED" if legacy_historical else "VERIFIED"
        ),
        "point_size": legacy_point if legacy_historical else None,
        "broker_symbol": manifest.get("broker_symbol") if legacy_historical else None,
        "provenance_status": (
            "LEGACY_PARTIAL_RUNTIME_SECURITY_AND_CONTRACT_METADATA"
            if legacy_historical else "CURRENT_SCHEMA"
        ),
        "symbols": output,
        "limitations": [
            "Descriptive XAUUSD tick profile only; not a trading signal or execution-readiness certification.",
            "Observed tick gaps can reflect market inactivity, broker feed behavior, or collection transport.",
            "No profitability, slippage, fill quality, or future quote availability is inferred.",
            *(
                [
                    "Legacy capture did not record runtime DLL-import state; the workflow log only proves the disabled setting was written, not that MT5 reported it effective.",
                    "Legacy capture records point size and broker symbol but not currency_base/currency_profit; no currency conversion or monetary PnL interpretation is permitted.",
                    "Legacy profile is permitted only for offline quote mechanics; candidate evaluation remains blocked by strict replay provenance checks.",
                ] if legacy_historical else []
            ),
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
