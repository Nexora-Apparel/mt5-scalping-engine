"""Read-only historical XAUUSD tick backfill probe for an authenticated Exness DEMO MT5 terminal.

This utility retrieves historical quotes only. It contains no order, position, or
trade-management calls. Historical quotes are research data, not execution fills.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.mt5_demo_tick_collector import (
    DEMO_TRADE_MODE, DiagnosticFailure, connect_expected_account,
    discover_symbol, utc_iso,
)

FIELDS = ["schema_version", "source_id", "canonical_symbol", "broker_symbol",
          "time_msc", "time_utc", "bid", "ask", "last", "volume",
          "volume_real", "flags"]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include Z or an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def probe(mt5: Any, start: datetime, end: datetime, output_dir: Path) -> dict[str, Any]:
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise DiagnosticFailure("a valid increasing UTC interval is required")
    login = int(os.environ.get("MT5_LOGIN", "0"))
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    terminal = os.environ.get("MT5_TERMINAL", r"C:\\MT5\\terminal64.exe")
    if login <= 0 or not password or not server:
        raise DiagnosticFailure("required MT5 credentials are missing")
    if not mt5.initialize(terminal, login=login, password=password, server=server,
                          timeout=120_000, portable=True):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")
    try:
        identity = connect_expected_account(mt5, login, password, server)
        if identity["trade_mode"] != DEMO_TRADE_MODE:
            raise DiagnosticFailure("historical probe requires a verified DEMO account")
        broker_symbol = discover_symbol(mt5, "XAUUSD")
        if not mt5.symbol_select(broker_symbol, True):
            raise DiagnosticFailure("could not select the discovered XAUUSD broker symbol")
        info = mt5.symbol_info(broker_symbol)
        if info is None:
            raise DiagnosticFailure("XAUUSD instrument metadata unavailable")

        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "xauusd_historical_ticks.csv"
        records = 0
        first_msc = last_msc = None
        previous = None
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\\n")
            writer.writeheader()
            cursor = start
            while cursor < end:
                batch = mt5.copy_ticks_range(broker_symbol, cursor, end, mt5.COPY_TICKS_ALL)
                if batch is None:
                    raise DiagnosticFailure(f"historical tick request failed; last_error={mt5.last_error()}")
                if len(batch) == 0:
                    break
                newest = None
                for tick in batch:
                    stamp = int(tick["time_msc"] if hasattr(tick, "dtype") and tick.dtype.names else tick.time_msc)
                    bid = float(tick["bid"] if hasattr(tick, "dtype") and tick.dtype.names else tick.bid)
                    ask = float(tick["ask"] if hasattr(tick, "dtype") and tick.dtype.names else tick.ask)
                    last = float(tick["last"] if hasattr(tick, "dtype") and tick.dtype.names else tick.last)
                    volume = float(tick["volume"] if hasattr(tick, "dtype") and tick.dtype.names else tick.volume)
                    volume_real = float(tick["volume_real"] if hasattr(tick, "dtype") and tick.dtype.names else tick.volume_real)
                    flags = int(tick["flags"] if hasattr(tick, "dtype") and tick.dtype.names else tick.flags)
                    if stamp <= 0 or bid <= 0 or ask < bid:
                        raise DiagnosticFailure("historical feed contains invalid timestamp or bid/ask")
                    if previous is not None and stamp < previous:
                        raise DiagnosticFailure("historical tick timestamps moved backwards")
                    previous = stamp
                    newest = stamp if newest is None else max(newest, stamp)
                    first_msc = stamp if first_msc is None else min(first_msc, stamp)
                    last_msc = stamp if last_msc is None else max(last_msc, stamp)
                    writer.writerow({"schema_version":"1","source_id":"exness_mt5_demo_historical",
                        "canonical_symbol":"XAUUSD","broker_symbol":broker_symbol,
                        "time_msc":stamp,"time_utc":utc_iso(stamp),"bid":repr(bid),"ask":repr(ask),
                        "last":repr(last),"volume":repr(volume),"volume_real":repr(volume_real),"flags":flags})
                    records += 1
                if newest is None:
                    break
                next_cursor = datetime.fromtimestamp(max(0, newest - 1) / 1000, tz=timezone.utc)
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(batch) < 10000:
                    break

        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        manifest = {
            "schema":"VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V1",
            "status":"PASS" if records else "FAIL",
            "source":"authenticated Exness MT5 DEMO terminal historical tick API",
            "account_mode":"DEMO","trading_enabled":False,"order_submission":False,
            "position_management":False,"canonical_symbol":"XAUUSD",
            "broker_symbol":broker_symbol,"requested_start_utc":start.isoformat(),
            "requested_end_utc":end.isoformat(),"records":records,
            "first_tick_utc":utc_iso(first_msc) if first_msc else None,
            "last_tick_utc":utc_iso(last_msc) if last_msc else None,
            "instrument_point":float(info.point),"sha256":digest,
            "csv_file":csv_path.name,
            "interpretation":"Historical bid/ask quotes are not actual broker fills; compare overlapping intervals against captured live evidence before treating sources as equivalent."
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
        if not records:
            raise DiagnosticFailure("no historical ticks returned for requested interval")
        return manifest
    finally:
        mt5.shutdown()


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-utc",required=True,help="ISO-8601 timestamp with Z or offset")
    parser.add_argument("--to-utc",required=True,help="ISO-8601 timestamp with Z or offset")
    parser.add_argument("--output-dir",type=Path,default=Path("historical-probe"))
    args=parser.parse_args()
    try:
        import MetaTrader5 as mt5
        result=probe(mt5,parse_utc(args.from_utc),parse_utc(args.to_utc),args.output_dir)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (DiagnosticFailure,ValueError,OSError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)}),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
