"""Read-only historical XAUUSD tick probe for an authenticated Exness DEMO MT5 terminal.

The probe requests bounded, non-overlapping UTC millisecond windows. It records
historical quotes only; these are not broker execution fills. No order or
position-management API is called.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools.mt5_demo_tick_collector import (
    DEMO_TRADE_MODE,
    DiagnosticFailure,
    connect_expected_account,
    discover_symbol,
    utc_iso,
    validate_account,
)

FIELDS = [
    "schema_version", "source_id", "canonical_symbol", "broker_symbol",
    "time_msc", "time_utc", "bid", "ask", "last", "volume",
    "volume_real", "flags",
]
CHUNK_MILLISECONDS = 60_000


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp with an explicit offset and normalize to UTC."""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("timestamp must be valid ISO-8601 with Z or an explicit UTC offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include Z or an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def _to_epoch_milliseconds(value: datetime, label: str) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DiagnosticFailure(f"{label} must include a timezone")
    utc_value = value.astimezone(timezone.utc)
    if utc_value.microsecond % 1000:
        raise DiagnosticFailure(f"{label} must be aligned to whole milliseconds")
    return int(utc_value.timestamp() * 1000)


def _tick_field(tick: Any, name: str) -> Any:
    """Read fields from MetaTrader5 numpy records and simple test doubles."""
    try:
        return tick[name]
    except (KeyError, IndexError, TypeError, ValueError):
        try:
            return getattr(tick, name)
        except AttributeError as exc:
            raise DiagnosticFailure(f"historical tick is missing field: {name}") from exc


def _normalize_tick(tick: Any, start_ms: int, end_ms: int) -> dict[str, Any]:
    try:
        stamp = int(_tick_field(tick, "time_msc"))
        bid = float(_tick_field(tick, "bid"))
        ask = float(_tick_field(tick, "ask"))
        last = float(_tick_field(tick, "last"))
        volume = float(_tick_field(tick, "volume"))
        volume_real = float(_tick_field(tick, "volume_real"))
        flags = int(_tick_field(tick, "flags"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise DiagnosticFailure("historical feed returned a malformed tick field") from exc

    if stamp < start_ms or stamp > end_ms:
        raise DiagnosticFailure("historical API returned a tick outside the requested UTC interval")
    if stamp <= 0 or not all(math.isfinite(v) for v in (bid, ask, last, volume, volume_real)):
        raise DiagnosticFailure("historical feed returned non-finite or invalid tick values")
    if bid <= 0 or ask < bid or volume < 0 or volume_real < 0:
        raise DiagnosticFailure("historical feed returned invalid bid/ask/volume values")

    return {
        "time_msc": stamp,
        "time_utc": utc_iso(stamp),
        "bid": repr(bid),
        "ask": repr(ask),
        "last": repr(last),
        "volume": repr(volume),
        "volume_real": repr(volume_real),
        "flags": flags,
    }


def probe(mt5: Any, start: datetime, end: datetime, output_dir: Path) -> dict[str, Any]:
    start_ms = _to_epoch_milliseconds(start, "start")
    end_ms = _to_epoch_milliseconds(end, "end")
    if start_ms >= end_ms:
        raise DiagnosticFailure("a valid increasing UTC interval is required")

    login = int(os.environ.get("MT5_LOGIN", "0"))
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    terminal = os.environ.get("MT5_TERMINAL", r"C:\MT5\terminal64.exe")
    if login <= 0 or not password or not server or not terminal:
        raise DiagnosticFailure("required MT5 configuration is missing")
    if not mt5.initialize(
        terminal, login=login, password=password, server=server,
        timeout=120_000, portable=True,
    ):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")

    try:
        identity = connect_expected_account(mt5, login, password, server)
        if identity.get("trade_mode") != DEMO_TRADE_MODE:
            raise DiagnosticFailure("historical probe requires a verified DEMO account")
        validate_account(mt5, login, server)

        broker_symbol = discover_symbol(mt5, "XAUUSD")
        info = mt5.symbol_info(broker_symbol)
        if info is None or not math.isfinite(float(getattr(info, "point", 0.0))) or float(info.point) <= 0:
            raise DiagnosticFailure("XAUUSD instrument metadata or point size is unavailable")

        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "xauusd_historical_ticks.csv"
        partial_path = output_dir / "xauusd_historical_ticks.csv.partial"
        manifest_path = output_dir / "manifest.json"
        # Never leave a stale successful manifest or dataset beside a failed rerun.
        for stale in (csv_path, partial_path, manifest_path):
            if stale.exists():
                stale.unlink()

        records_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
        chunks: list[dict[str, Any]] = []
        cursor_ms = start_ms
        try:
            with partial_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()

                while cursor_ms <= end_ms:
                    chunk_end_ms = min(cursor_ms + CHUNK_MILLISECONDS - 1, end_ms)
                    validate_account(mt5, login, server)
                    chunk_start = datetime.fromtimestamp(cursor_ms / 1000, tz=timezone.utc)
                    chunk_end = datetime.fromtimestamp(chunk_end_ms / 1000, tz=timezone.utc)
                    batch = mt5.copy_ticks_range(
                        broker_symbol, chunk_start, chunk_end, mt5.COPY_TICKS_ALL
                    )
                    if batch is None:
                        raise DiagnosticFailure(
                            "historical tick request failed; "
                            f"last_error={mt5.last_error()}; "
                            f"chunk={chunk_start.isoformat()}..{chunk_end.isoformat()}"
                        )

                    chunk_rows = [
                        _normalize_tick(tick, cursor_ms, chunk_end_ms) for tick in batch
                    ]
                    # Preserve provider order for ticks sharing a millisecond while
                    # making the chunk's timestamp order deterministic.
                    chunk_rows.sort(key=lambda row: row["time_msc"])
                    for row in chunk_rows:
                        key = (
                            row["time_msc"], row["bid"], row["ask"], row["last"],
                            row["volume"], row["volume_real"], row["flags"],
                        )
                        records_by_key[key] = row

                    chunks.append({
                        "start_utc": chunk_start.isoformat(),
                        "end_utc": chunk_end.isoformat(),
                        "returned_records": len(batch),
                        "unique_records": len({
                            (
                                row["time_msc"], row["bid"], row["ask"], row["last"],
                                row["volume"], row["volume_real"], row["flags"],
                            ) for row in chunk_rows
                        }),
                    })
                    cursor_ms = chunk_end_ms + 1

                ordered_rows = sorted(
                    records_by_key.values(),
                    key=lambda row: (
                        row["time_msc"], row["bid"], row["ask"], row["last"],
                        row["volume"], row["volume_real"], row["flags"],
                    ),
                )
                previous_ms = None
                for row in ordered_rows:
                    stamp = row["time_msc"]
                    if previous_ms is not None and stamp < previous_ms:
                        raise DiagnosticFailure("historical tick timestamps moved backwards")
                    previous_ms = stamp
                    writer.writerow({
                        "schema_version": "1",
                        "source_id": "exness_mt5_demo_historical",
                        "canonical_symbol": "XAUUSD",
                        "broker_symbol": broker_symbol,
                        **row,
                    })
                handle.flush()
                os.fsync(handle.fileno())

            if not records_by_key:
                raise DiagnosticFailure("no historical ticks returned for requested interval")
            partial_path.replace(csv_path)
        except Exception:
            if partial_path.exists():
                partial_path.unlink()
            raise

        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        ordered_stamps = [row["time_msc"] for row in records_by_key.values()]
        manifest = {
            "schema": "VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V2",
            "status": "PASS",
            "source": "authenticated Exness MT5 DEMO terminal historical tick API",
            "account_mode": "DEMO",
            "trading_enabled": False,
            "order_submission": False,
            "position_management": False,
            "canonical_symbol": "XAUUSD",
            "broker_symbol": broker_symbol,
            "requested_start_utc": datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat(),
            "requested_end_utc": datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat(),
            "interval_semantics": "inclusive UTC millisecond bounds",
            "retrieval_chunk_milliseconds": CHUNK_MILLISECONDS,
            "chunks_requested": len(chunks),
            "chunks": chunks,
            "records": len(records_by_key),
            "first_tick_utc": utc_iso(min(ordered_stamps)),
            "last_tick_utc": utc_iso(max(ordered_stamps)),
            "instrument_point": float(info.point),
            "sha256": digest,
            "csv_file": csv_path.name,
            "interpretation": (
                "Historical bid/ask quotes are not actual broker fills. "
                "Compare overlapping intervals against captured live evidence "
                "before treating sources as equivalent."
            ),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-utc", required=True, help="ISO-8601 timestamp with Z or offset")
    parser.add_argument("--to-utc", required=True, help="ISO-8601 timestamp with Z or offset")
    parser.add_argument("--output-dir", type=Path, default=Path("historical-probe"))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
        result = probe(mt5, parse_utc(args.from_utc), parse_utc(args.to_utc), args.output_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (DiagnosticFailure, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
