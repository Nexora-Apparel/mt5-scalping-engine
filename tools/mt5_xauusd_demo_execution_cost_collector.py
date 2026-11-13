"""Read-only Exness DEMO XAUUSD execution-cost evidence collector.

Captures broker account/symbol specifications and sanitized historical deals.
It never sends, checks, modifies, or manages orders. Deal observations are
corroborating evidence only; they do not independently establish a commission
schedule or unlock net-performance scoring.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import secrets
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mt5_python_readonly_diagnostic import (
    DEMO_TRADE_MODE, DiagnosticFailure, discover_symbol, validate_account,
)

DEAL_FIELDS = [
    "position_ref", "time_msc", "time_utc", "deal_type", "deal_entry",
    "volume_lots", "price", "commission_usd", "fee_usd", "swap_usd",
    "profit_usd", "symbol",
]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _finite(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DiagnosticFailure(f"deal contains invalid {field}") from exc
    if not math.isfinite(result):
        raise DiagnosticFailure(f"deal contains non-finite {field}")
    return result


def _utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _position_ref(position_id: int, package_salt: bytes) -> str:
    # Per-package HMAC prevents public brute-force enumeration of broker IDs and
    # prevents correlation of the same position across separate collection runs.
    return hashlib.sha256(package_salt + str(position_id).encode()).hexdigest()


def _deal_entry_name(value: int, mt5: Any) -> str:
    mapping = {
        int(getattr(mt5, "DEAL_ENTRY_IN", 0)): "IN",
        int(getattr(mt5, "DEAL_ENTRY_OUT", 1)): "OUT",
        int(getattr(mt5, "DEAL_ENTRY_INOUT", 2)): "INOUT",
        int(getattr(mt5, "DEAL_ENTRY_OUT_BY", 3)): "OUT_BY",
    }
    return mapping.get(value, f"UNKNOWN_{value}")


def _deal_type_name(value: int, mt5: Any) -> str:
    mapping = {
        int(getattr(mt5, "DEAL_TYPE_BUY", 0)): "BUY",
        int(getattr(mt5, "DEAL_TYPE_SELL", 1)): "SELL",
    }
    return mapping.get(value, f"OTHER_{value}")


def collect_evidence(
    mt5: Any,
    output_dir: Path,
    *,
    days: int = 365,
    now=lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
        raise DiagnosticFailure("history window must be between 1 and 3650 days")
    login_raw = os.environ.get("MT5_LOGIN", "")
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    terminal = os.environ.get("MT5_TERMINAL", r"C:\\MT5\\terminal64.exe")
    try:
        login = int(login_raw)
    except ValueError as exc:
        raise DiagnosticFailure("MT5_LOGIN is missing or invalid") from exc
    if login <= 0 or not password or not server or not terminal:
        raise DiagnosticFailure("required MT5 connection configuration is missing")
    if not mt5.initialize(terminal, login=login, password=password, server=server,
                          timeout=120_000, portable=True):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")
    try:
        identity = validate_account(mt5, login, server)
        if identity["trade_mode"] != DEMO_TRADE_MODE:
            raise DiagnosticFailure("execution-cost evidence requires a DEMO account")
        account = mt5.account_info()
        symbol = discover_symbol(mt5, "XAUUSD")
        info = mt5.symbol_info(symbol)
        if info is None:
            raise DiagnosticFailure("XAUUSD broker symbol specification is unavailable")
        currency_profit = str(_get(info, "currency_profit", "") or "").upper()
        account_currency = str(_get(account, "currency", "") or "").upper()
        contract_size = _finite(_get(info, "trade_contract_size", 0), "contract size")
        if currency_profit != "USD" or account_currency != "USD" or contract_size <= 0:
            raise DiagnosticFailure("XAUUSD profit currency, DEMO account currency, or contract size is not verified")
        captured = now().astimezone(timezone.utc)
        start = captured - timedelta(days=days)
        deals = mt5.history_deals_get(start, captured)
        if deals is None:
            raise DiagnosticFailure(f"history_deals_get failed; last_error={mt5.last_error()}")

        # This salt is deliberately not exported. Position references are useful
        # only for joining rows within this evidence package.
        package_salt = secrets.token_bytes(32)
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        sanitized: list[dict[str, Any]] = []
        for deal in deals:
            if str(_get(deal, "symbol", "") or "") != symbol:
                continue
            position_id = int(_get(deal, "position_id", 0) or 0)
            stamp = int(_get(deal, "time_msc", 0) or 0)
            if position_id <= 0 or stamp <= 0:
                raise DiagnosticFailure("matching XAUUSD deal is missing position identity or timestamp")
            entry_value = int(_get(deal, "entry", -1))
            type_value = int(_get(deal, "type", -1))
            row = {
                "position_ref": _position_ref(position_id, package_salt),
                "time_msc": stamp,
                "time_utc": _utc(stamp),
                "deal_type": _deal_type_name(type_value, mt5),
                "deal_entry": _deal_entry_name(entry_value, mt5),
                "volume_lots": _finite(_get(deal, "volume", 0), "volume"),
                "price": _finite(_get(deal, "price", 0), "price"),
                "commission_usd": _finite(_get(deal, "commission", 0), "commission"),
                "fee_usd": _finite(_get(deal, "fee", 0), "fee"),
                "swap_usd": _finite(_get(deal, "swap", 0), "swap"),
                "profit_usd": _finite(_get(deal, "profit", 0), "profit"),
                "symbol": symbol,
            }
            if row["volume_lots"] <= 0 or row["price"] <= 0:
                raise DiagnosticFailure("matching XAUUSD deal has invalid volume or price")
            sanitized.append(row)
            grouped[position_id].append(row)

        round_trips = []
        for position_id, rows in sorted(grouped.items()):
            entries = [row for row in rows if row["deal_entry"] == "IN"]
            exits = [row for row in rows if row["deal_entry"] in ("OUT", "OUT_BY")]
            ambiguous = any(row["deal_entry"] in ("INOUT",) or row["deal_entry"].startswith("UNKNOWN") for row in rows)
            opened = sum(row["volume_lots"] for row in entries)
            closed = sum(row["volume_lots"] for row in exits)
            is_closed = bool(entries and exits and not ambiguous and closed + 1e-8 >= opened)
            commission = sum(row["commission_usd"] for row in rows)
            round_trips.append({
                "position_ref": _position_ref(position_id, package_salt),
                "entry_deal_count": len(entries),
                "exit_deal_count": len(exits),
                "opened_volume_lots": round(opened, 8),
                "closed_volume_lots": round(closed, 8),
                "round_trip_complete_in_export": is_closed,
                "commission_total_usd_signed": round(commission, 8),
                "observed_round_turn_commission_usd_per_lot": (
                    round(abs(commission) / opened, 8) if is_closed and opened > 0 else None
                ),
                "observed_commission_usd_per_lot_per_side_equivalent": (
                    round(abs(commission) / (2 * opened), 8) if is_closed and opened > 0 else None
                ),
                "commission_observation_status": (
                    "OBSERVED_COMPLETED_DEMO_POSITION_NOT_A_SCHEDULE"
                    if is_closed else "INCOMPLETE_OR_AMBIGUOUS_POSITION"
                ),
                "fee_total_usd_signed": round(sum(row["fee_usd"] for row in rows), 8),
                "swap_total_usd_signed": round(sum(row["swap_usd"] for row in rows), 8),
                "profit_total_usd_signed": round(sum(row["profit_usd"] for row in rows), 8),
            })

        output_dir.mkdir(parents=True, exist_ok=True)
        deals_path = output_dir / "demo_deals_sanitized.csv"
        with deals_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DEAL_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(sanitized, key=lambda row: (row["time_msc"], row["position_ref"])))
        spec_snapshot = {
            "canonical_symbol": "XAUUSD",
            "broker_symbol": symbol,
            "currency_base": str(_get(info, "currency_base", "") or ""),
            "currency_profit": currency_profit,
            "account_currency": account_currency,
            "contract_size_oz_per_lot": contract_size,
            "point": _finite(_get(info, "point", 0), "point"),
            "digits": int(_get(info, "digits", 0)),
            "trade_tick_size": _finite(_get(info, "trade_tick_size", 0), "tick size"),
            "trade_tick_value": _finite(_get(info, "trade_tick_value", 0), "tick value"),
            "volume_min": _finite(_get(info, "volume_min", 0), "minimum volume"),
            "volume_max": _finite(_get(info, "volume_max", 0), "maximum volume"),
            "volume_step": _finite(_get(info, "volume_step", 0), "volume step"),
        }
        account_snapshot = {
            "account_mode": "DEMO",
            "server": str(_get(account, "server", "")),
            "company": str(_get(account, "company", "")),
            "currency": account_currency,
            "terminal_connected": identity["connected"],
            "terminal_trade_allowed": identity["terminal_trade_allowed"],
            "terminal_dlls_allowed": identity["terminal_dlls_allowed"],
            "login_persisted": False,
        }
        (output_dir / "broker_account_snapshot.json").write_text(
            json.dumps(account_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output_dir / "symbol_spec_snapshot.json").write_text(
            json.dumps(spec_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary = {
            "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_OBSERVATIONS_V1",
            "status": "OBSERVATIONS_CAPTURED" if sanitized else "NEEDS_DEMO_DEAL_HISTORY",
            "captured_at_utc": captured.isoformat(),
            "history_window_start_utc": start.isoformat(),
            "history_window_end_utc": captured.isoformat(),
            "history_window_days": days,
            "account_mode": "DEMO",
            "broker_symbol": symbol,
            "account_currency": account_currency,
            "deal_count_xauusd": len(sanitized),
            "position_count": len(grouped),
            "complete_round_trip_position_count": sum(item["round_trip_complete_in_export"] for item in round_trips),
            "round_trip_observations": round_trips,
            "commission_schedule_status": "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW",
            "net_performance_allowed": False,
            "limitations": [
                "Historical DEMO deal charges are observations, not a broker commission schedule.",
                "Only XAUUSD deals present in the selected history window are included.",
                "Positions opened before the history window may be incomplete and are not used for round-turn estimates.",
                "No orders are sent, checked, modified, or managed by this collector.",
                "No commission evidence is marked independently verified by this collector.",
            ],
        }
        (output_dir / "round_trip_cost_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = {}
        package_files = (
            "broker_account_snapshot.json",
            "symbol_spec_snapshot.json",
            "demo_deals_sanitized.csv",
            "round_trip_cost_summary.json",
        )
        for name in package_files:
            path = output_dir / name
            if not path.is_file():
                raise DiagnosticFailure(f"required execution-cost package file is missing: {name}")
            files[name] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        manifest = {
            "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_PACKAGE_V1",
            "status": summary["status"],
            "captured_at_utc": captured.isoformat(),
            "account_mode": "DEMO",
            "broker_symbol": symbol,
            "position_reference_scheme": "PER_PACKAGE_SALTED_SHA256",
            "position_reference_salt_sha256": hashlib.sha256(package_salt).hexdigest(),
            "files": files,
            "commission_schedule_status": summary["commission_schedule_status"],
            "net_performance_allowed": False,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output-dir", type=Path, default=Path("session-artifacts/execution-cost-evidence"))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
        result = collect_evidence(mt5, args.output_dir, days=args.days)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0
    except (DiagnosticFailure, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
