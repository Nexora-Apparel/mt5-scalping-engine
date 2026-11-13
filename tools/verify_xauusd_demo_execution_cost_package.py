"""Independent integrity verifier for sanitized XAUUSD DEMO execution-cost packages."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_FILES = {
    "broker_account_snapshot.json",
    "symbol_spec_snapshot.json",
    "demo_deals_sanitized.csv",
    "round_trip_cost_summary.json",
}
DEAL_FIELDS = [
    "position_ref", "time_msc", "time_utc", "deal_type", "deal_entry",
    "volume_lots", "price", "commission_usd", "fee_usd", "swap_usd",
    "profit_usd", "symbol",
]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PackageVerificationError(ValueError):
    """Raised when an execution-cost evidence package is incomplete or altered."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageVerificationError(f"{path.name} is unreadable JSON") from exc
    if not isinstance(value, dict):
        raise PackageVerificationError(f"{path.name} must contain a JSON object")
    return value


def verify_package(package_dir: Path) -> dict[str, Any]:
    if not isinstance(package_dir, Path) or not package_dir.is_dir():
        raise PackageVerificationError("execution-cost package directory is missing")
    manifest = _read_json(package_dir / "manifest.json")
    if manifest.get("schema") != "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_PACKAGE_V1":
        raise PackageVerificationError("unsupported execution-cost package schema")
    if manifest.get("account_mode") != "DEMO" or manifest.get("net_performance_allowed") is not False:
        raise PackageVerificationError("package must remain DEMO-only with net scoring disabled")
    if manifest.get("commission_schedule_status") != "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW":
        raise PackageVerificationError("package cannot assert commission schedule verification")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != EXPECTED_FILES:
        raise PackageVerificationError("manifest must hash exactly the four required evidence files")
    for name, metadata in files.items():
        path = package_dir / name
        if not path.is_file() or not isinstance(metadata, dict):
            raise PackageVerificationError(f"manifest file is missing: {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if metadata.get("sha256") != digest or metadata.get("bytes") != path.stat().st_size:
            raise PackageVerificationError(f"package file hash or byte count mismatch: {name}")

    account = _read_json(package_dir / "broker_account_snapshot.json")
    spec = _read_json(package_dir / "symbol_spec_snapshot.json")
    summary = _read_json(package_dir / "round_trip_cost_summary.json")
    if account.get("account_mode") != "DEMO" or account.get("login_persisted") is not False:
        raise PackageVerificationError("account snapshot is not sanitized Exness DEMO evidence")
    if account.get("terminal_connected") is not True or account.get("terminal_trade_allowed") is not False or account.get("terminal_dlls_allowed") is not False:
        raise PackageVerificationError("terminal read-only controls are not proven by account snapshot")
    symbol = manifest.get("broker_symbol")
    if not isinstance(symbol, str) or not symbol or summary.get("broker_symbol") != symbol or spec.get("broker_symbol") != symbol:
        raise PackageVerificationError("broker symbol differs across package components")
    if spec.get("canonical_symbol") != "XAUUSD" or spec.get("currency_base") != "XAU":
        raise PackageVerificationError("package instrument is not canonical XAUUSD")
    if spec.get("currency_profit") != "USD" or spec.get("account_currency") != "USD" or account.get("currency") != "USD":
        raise PackageVerificationError("account and instrument currencies must be USD")
    contract = spec.get("contract_size_oz_per_lot")
    if isinstance(contract, bool) or not isinstance(contract, (int, float)) or not math.isfinite(contract) or contract <= 0:
        raise PackageVerificationError("verified broker contract size is missing")
    if summary.get("schema") != "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_OBSERVATIONS_V1":
        raise PackageVerificationError("unsupported deal-observation summary schema")
    if summary.get("status") not in ("OBSERVATIONS_CAPTURED", "NEEDS_DEMO_DEAL_HISTORY"):
        raise PackageVerificationError("deal-observation status is invalid")
    if summary.get("commission_schedule_status") != manifest["commission_schedule_status"] or summary.get("net_performance_allowed") is not False:
        raise PackageVerificationError("summary attempts to unlock commission or net scoring")

    rows = []
    try:
        with (package_dir / "demo_deals_sanitized.csv").open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != DEAL_FIELDS:
                raise PackageVerificationError("sanitized deal CSV columns do not match the approved schema")
            rows = list(reader)
    except OSError as exc:
        raise PackageVerificationError("sanitized deal CSV is unreadable") from exc
    for index, row in enumerate(rows, start=2):
        if row.get("symbol") != symbol or not _SHA256.fullmatch(row.get("position_ref", "")):
            raise PackageVerificationError(f"deal row {index} has an invalid symbol or position reference")
        try:
            stamp = int(row["time_msc"])
            numeric = [float(row[key]) for key in ("volume_lots", "price", "commission_usd", "fee_usd", "swap_usd", "profit_usd")]
        except (KeyError, TypeError, ValueError) as exc:
            raise PackageVerificationError(f"deal row {index} has invalid numeric data") from exc
        if stamp <= 0 or not all(math.isfinite(value) for value in numeric) or numeric[0] <= 0 or numeric[1] <= 0:
            raise PackageVerificationError(f"deal row {index} contains non-finite or non-positive values")
        if row.get("deal_entry") not in ("IN", "OUT", "INOUT", "OUT_BY") and not row.get("deal_entry", "").startswith("UNKNOWN_"):
            raise PackageVerificationError(f"deal row {index} has an invalid entry classification")

    if summary.get("deal_count_xauusd") != len(rows):
        raise PackageVerificationError("summary deal count does not match sanitized CSV")
    observations = summary.get("round_trip_observations")
    if not isinstance(observations, list) or summary.get("position_count") != len(observations):
        raise PackageVerificationError("position summary count does not match observations")
    complete = sum(item.get("round_trip_complete_in_export") is True for item in observations if isinstance(item, dict))
    if summary.get("complete_round_trip_position_count") != complete:
        raise PackageVerificationError("complete round-trip count does not match position summaries")
    return {
        "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_VERIFICATION_V1",
        "status": "VERIFIED_PACKAGE",
        "account_mode": "DEMO",
        "broker_symbol": symbol,
        "deal_count_xauusd": len(rows),
        "position_count": len(observations),
        "complete_round_trip_position_count": complete,
        "manifest_sha256": hashlib.sha256((package_dir / "manifest.json").read_bytes()).hexdigest(),
        "commission_schedule_status": "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW",
        "net_performance_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = verify_package(args.package_dir)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (PackageVerificationError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
