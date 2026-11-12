"""Bounded, read-only Exness DEMO tick collector for XAUUSD and XAGUSD.

The collector verifies DEMO identity throughout the session, requires terminal
trading/DLL permissions to remain disabled, resolves contracts from the broker
catalogue, records UTC tick data, and audits the immutable CSV before success.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mt5_python_readonly_diagnostic import (
    CANONICAL_SYMBOLS, DEMO_TRADE_MODE, DiagnosticFailure,
    discover_symbol, validate_account, validate_quote,
)

HEADER = [
    "schema_version", "source_id", "canonical_symbol", "broker_symbol",
    "time_msc", "time_utc", "bid", "ask", "last", "volume",
    "volume_real", "flags",
]
BATCH_SIZE = 10_000


def utc_iso(time_msc: int) -> str:
    return datetime.fromtimestamp(time_msc / 1000, tz=timezone.utc).isoformat()


def _field(tick: Any, name: str, default: Any = 0) -> Any:
    try:
        return tick[name]
    except (KeyError, IndexError, TypeError, ValueError):
        return getattr(tick, name, default)


def _tick_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["time_msc"], row["bid"], row["ask"], row["last"],
        row["volume"], row["volume_real"], row["flags"],
    )


def audit_ticks(path: str | Path, expected_symbols: tuple[str, ...] = CANONICAL_SYMBOLS) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise DiagnosticFailure("tick dataset is missing or empty")
    counts = {symbol: 0 for symbol in expected_symbols}
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    previous: dict[str, int] = {}
    max_gap_ms: dict[str, int] = {symbol: 0 for symbol in expected_symbols}
    gaps_over_5s: dict[str, int] = {symbol: 0 for symbol in expected_symbols}
    seen: set[tuple[Any, ...]] = set()
    rows = 0

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADER:
            raise DiagnosticFailure("tick CSV header does not match schema")
        for line, row in enumerate(reader, start=2):
            if None in row or any(row.get(k) in (None, "") for k in HEADER):
                raise DiagnosticFailure(f"line {line}: missing or extra fields")
            if row["schema_version"] != "1":
                raise DiagnosticFailure(f"line {line}: unsupported schema version")
            symbol = row["canonical_symbol"]
            if symbol not in counts:
                raise DiagnosticFailure(f"line {line}: unexpected canonical symbol {symbol}")
            try:
                stamp = int(row["time_msc"])
                bid, ask = float(row["bid"]), float(row["ask"])
                last_price = float(row["last"])
                volume, volume_real = float(row["volume"]), float(row["volume_real"])
                int(row["flags"])
            except (TypeError, ValueError) as exc:
                raise DiagnosticFailure(f"line {line}: invalid numeric tick field") from exc
            if stamp <= 0 or not all(math.isfinite(v) for v in (bid, ask, last_price, volume, volume_real)):
                raise DiagnosticFailure(f"line {line}: non-finite or invalid tick values")
            if bid <= 0 or ask < bid or volume < 0 or volume_real < 0:
                raise DiagnosticFailure(f"line {line}: invalid bid/ask/volume")
            if row["time_utc"] != utc_iso(stamp):
                raise DiagnosticFailure(f"line {line}: UTC timestamp does not match epoch milliseconds")
            if not row["source_id"] or not row["broker_symbol"]:
                raise DiagnosticFailure(f"line {line}: missing source or broker symbol")
            identity = (symbol, *_tick_key({
                "time_msc": stamp, "bid": bid, "ask": ask, "last": last_price,
                "volume": volume, "volume_real": volume_real, "flags": int(row["flags"]),
            }))
            if identity in seen:
                raise DiagnosticFailure(f"line {line}: duplicate tick record")
            seen.add(identity)
            if symbol in previous and stamp < previous[symbol]:
                raise DiagnosticFailure(f"line {line}: tick timestamps moved backwards for {symbol}")
            if symbol in previous:
                gap = stamp - previous[symbol]
                max_gap_ms[symbol] = max(max_gap_ms[symbol], gap)
                if gap > 5_000:
                    gaps_over_5s[symbol] += 1
            previous[symbol] = stamp
            first.setdefault(symbol, stamp)
            last[symbol] = stamp
            counts[symbol] += 1
            rows += 1

    missing = [symbol for symbol, count in counts.items() if count == 0]
    if missing:
        raise DiagnosticFailure(f"no tick records collected for: {','.join(missing)}")
    raw = source.read_bytes()
    return {
        "status": "PASS",
        "schema_version": "1",
        "dataset": source.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "records": rows,
        "streams": {
            symbol: {
                "records": counts[symbol],
                "first_time_msc": first[symbol],
                "first_time_utc": utc_iso(first[symbol]),
                "last_time_msc": last[symbol],
                "last_time_utc": utc_iso(last[symbol]),
                "max_intertick_gap_ms": max_gap_ms[symbol],
                "gaps_over_5_seconds": gaps_over_5s[symbol],
            } for symbol in expected_symbols
        },
    }


def _collect_symbol_ticks(
    mt5: Any, canonical: str, broker_symbol: str, source_id: str,
    cursor: datetime, records: dict[tuple[Any, ...], dict[str, Any]],
    minimum_time_msc: int,
) -> datetime:
    next_cursor = cursor
    while True:
        batch = mt5.copy_ticks_from(
            broker_symbol, next_cursor, BATCH_SIZE, mt5.COPY_TICKS_ALL
        )
        if batch is None:
            raise DiagnosticFailure(
                f"{canonical}: copy_ticks_from failed; last_error={mt5.last_error()}"
            )
        if len(batch) == 0:
            break
        ordered = sorted(batch, key=lambda tick: int(_field(tick, "time_msc", 0)))
        newest = 0
        for tick in ordered:
            stamp = int(_field(tick, "time_msc", 0))
            bid = float(_field(tick, "bid", 0.0))
            ask = float(_field(tick, "ask", 0.0))
            last_price = float(_field(tick, "last", 0.0))
            volume = float(_field(tick, "volume", 0.0))
            volume_real = float(_field(tick, "volume_real", 0.0))
            flags = int(_field(tick, "flags", 0))
            if stamp <= 0 or not all(math.isfinite(v) for v in (bid, ask, last_price, volume, volume_real)):
                raise DiagnosticFailure(f"{canonical}: broker returned malformed tick data")
            if bid <= 0 or ask < bid or volume < 0 or volume_real < 0:
                raise DiagnosticFailure(f"{canonical}: broker returned invalid bid/ask/volume")
            if stamp < minimum_time_msc:
                newest = max(newest, stamp)
                continue
            row = {
                "schema_version": "1", "source_id": source_id,
                "canonical_symbol": canonical, "broker_symbol": broker_symbol,
                "time_msc": stamp, "time_utc": utc_iso(stamp),
                "bid": repr(bid), "ask": repr(ask), "last": repr(last_price),
                "volume": repr(volume), "volume_real": repr(volume_real),
                "flags": flags,
            }
            records[(canonical, *_tick_key(row))] = row
            newest = max(newest, stamp)
        if newest <= 0:
            break
        # Advance after every non-empty batch, not only a full batch. The
        # one-millisecond overlap preserves same-ms ticks; record keys dedupe.
        candidate = datetime.fromtimestamp(newest / 1000, tz=timezone.utc) - timedelta(milliseconds=1)
        if candidate <= next_cursor:
            break
        next_cursor = candidate
        if len(batch) < BATCH_SIZE:
            break
    return next_cursor


def collect(mt5: Any, minutes: int, output_dir: Path, *,
            monotonic=time.monotonic, sleep=time.sleep, now=lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    if minutes != 30:
        raise DiagnosticFailure("only the bounded 30-minute collection is enabled")
    login = int(os.environ.get("MT5_LOGIN", "0"))
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    terminal = os.environ.get("MT5_TERMINAL", r"C:\MT5\terminal64.exe")
    if login <= 0 or not password or not server or not terminal:
        raise DiagnosticFailure("required MT5 configuration is missing")
    if not mt5.initialize(terminal, login=login, password=password, server=server,
                          timeout=120_000, portable=True):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")

    try:
        identity = validate_account(mt5, login, server)
        if identity["trade_mode"] != DEMO_TRADE_MODE:
            raise DiagnosticFailure("account is not DEMO")
        symbols = {name: discover_symbol(mt5, name) for name in CANONICAL_SYMBOLS}
        instrument_specs = {}
        for canonical, broker_symbol in symbols.items():
            info = mt5.symbol_info(broker_symbol)
            if info is None or float(getattr(info, "point", 0.0)) <= 0:
                raise DiagnosticFailure(f"{canonical}: broker instrument specification unavailable")
            instrument_specs[canonical] = {
                "broker_symbol": broker_symbol,
                "point": float(info.point),
                "digits": int(getattr(info, "digits", 0)),
                "currency_base": str(getattr(info, "currency_base", "") or ""),
                "currency_profit": str(getattr(info, "currency_profit", "") or ""),
                "trade_tick_size": float(getattr(info, "trade_tick_size", 0.0) or 0.0),
                "trade_contract_size": float(getattr(info, "trade_contract_size", 0.0) or 0.0),
            }
        spread_samples = {name: [] for name in CANONICAL_SYMBOLS}
        source_id = "exness-demo-" + re.sub(r"[^A-Za-z0-9_-]", "-", server)[:70]
        started_utc = now()
        start_mono = monotonic()
        start_time_msc = int(started_utc.timestamp() * 1000)
        cursors = {name: started_utc - timedelta(seconds=2) for name in CANONICAL_SYMBOLS}
        records: dict[tuple[Any, ...], dict[str, Any]] = {}
        quote_samples = 0
        deadline = start_mono + minutes * 60
        while monotonic() < deadline:
            validate_account(mt5, login, server)
            current_ms = int(now().timestamp() * 1000)
            for canonical in CANONICAL_SYMBOLS:
                quote = validate_quote(mt5, symbols[canonical], current_ms, 15_000, 1_000, canonical)
                spread_samples[canonical].append(quote["spread_points"])
                cursors[canonical] = _collect_symbol_ticks(
                    mt5, canonical, symbols[canonical], source_id,
                    cursors[canonical], records, start_time_msc,
                )
            quote_samples += 1
            sleep(min(1.0, max(0.0, deadline - monotonic())))

        ended_utc = now()
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "veltrix_exness_demo_ticks.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
            writer.writeheader()
            ordered = sorted(records.values(), key=lambda row: (
                row["canonical_symbol"], row["time_msc"], row["bid"], row["ask"],
                row["last"], row["volume"], row["volume_real"], row["flags"],
            ))
            writer.writerows(ordered)
            handle.flush()
            os.fsync(handle.fileno())

        audit = audit_ticks(csv_path)
        manifest = {
            **audit,
            "collection_started_utc": started_utc.isoformat(),
            "collection_ended_utc": ended_utc.isoformat(),
            "duration_seconds": round((ended_utc - started_utc).total_seconds(), 3),
            "requested_duration_minutes": minutes,
            "quote_validation_cycles": quote_samples,
            "account_mode": "DEMO",
            "server": server,
            "symbols": symbols,
            "instrument_specs": instrument_specs,
            "spread_points": {
                name: {
                    "samples": len(values),
                    "minimum": min(values),
                    "maximum": max(values),
                    "mean": round(sum(values) / len(values), 4),
                } for name, values in spread_samples.items() if values
            },
            "trading_enabled": False,
            "dll_imports_enabled": False,
            "collection_method": "MetaQuotes copy_ticks_from / COPY_TICKS_ALL",
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if manifest["duration_seconds"] < 30 * 60:
            raise DiagnosticFailure("collection duration was shorter than the required 30 minutes")
        return manifest
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("session-artifacts"))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
        manifest = collect(mt5, args.minutes, args.output_dir)
        print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
        return 0
    except (DiagnosticFailure, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)},
                         ), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
