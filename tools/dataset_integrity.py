#!/usr/bin/env python3
"""Strict integrity validator for VELTRIX point-in-time feature CSV exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HEADER = [
    "schema_version", "feature_version", "source_id", "symbol",
    "quote_time_msc", "window_start_msc", "evaluation_time_msc",
    "bid", "ask", "momentum_bps", "realized_volatility_bps",
    "efficiency_ratio", "observations",
]
SCHEMA_VERSION = "1"
FEATURE_VERSION = "1.0.0"
SYMBOLS = {"XAUUSD", "XAGUSD"}


class DatasetIntegrityError(ValueError):
    """Raised when a dataset cannot be trusted for chronological research."""


def _integer(value: str | None, field: str, line: int) -> int:
    if value is None or not re.fullmatch(r"[0-9]+", value):
        raise DatasetIntegrityError(f"line {line}: {field} must be an unsigned integer")
    return int(value)


def _number(value: str | None, field: str, line: int) -> float:
    if value is None or value.strip() == "":
        raise DatasetIntegrityError(f"line {line}: {field} is missing")
    try:
        result = float(value)
    except ValueError as exc:
        raise DatasetIntegrityError(f"line {line}: {field} is not numeric") from exc
    if not math.isfinite(result):
        raise DatasetIntegrityError(f"line {line}: {field} must be finite")
    return result


def _utc(ms: int) -> str:
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise DatasetIntegrityError(f"timestamp {ms} is outside the supported UTC range") from exc


def audit_dataset(path: str | Path) -> dict[str, Any]:
    """Validate a complete dataset and return a reproducible integrity manifest.

    No row is repaired, reordered, deduplicated, imputed, or silently discarded.
    Chronology is checked independently for each (source_id, symbol) stream.
    """
    source = Path(path)
    if not source.is_file():
        raise DatasetIntegrityError(f"dataset does not exist: {source}")
    raw = source.read_bytes()
    if not raw:
        raise DatasetIntegrityError("dataset is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetIntegrityError("dataset must be UTF-8 (optional BOM is accepted)") from exc

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        header = reader.fieldnames
        if header != EXPECTED_HEADER:
            raise DatasetIntegrityError(
                f"header mismatch: expected {EXPECTED_HEADER!r}, received {header!r}"
            )

        seen: set[tuple[str, str, int]] = set()
        last_eval: dict[tuple[str, str], int] = {}
        grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
        schema_versions: set[str] = set()
        feature_versions: set[str] = set()
        rows = 0

        for line, row in enumerate(reader, start=2):
            if row is None or all(value is None or value == "" for value in row.values()):
                raise DatasetIntegrityError(f"line {line}: blank records are not permitted")
            if None in row or any(row.get(key) is None for key in EXPECTED_HEADER):
                raise DatasetIntegrityError(f"line {line}: row has missing or extra CSV fields")

            schema = row["schema_version"]
            feature = row["feature_version"]
            source_id = row["source_id"]
            symbol = row["symbol"]
            if schema != SCHEMA_VERSION:
                raise DatasetIntegrityError(f"line {line}: unsupported schema_version {schema!r}")
            if feature != FEATURE_VERSION:
                raise DatasetIntegrityError(f"line {line}: unsupported feature_version {feature!r}")
            if (not source_id or len(source_id) > 96 or source_id.strip() != source_id or
                "," in source_id or any(ord(c) < 32 for c in source_id)):
                raise DatasetIntegrityError(f"line {line}: invalid source_id")
            if symbol not in SYMBOLS:
                raise DatasetIntegrityError(f"line {line}: unsupported symbol {symbol!r}")

            quote_ms = _integer(row["quote_time_msc"], "quote_time_msc", line)
            window_ms = _integer(row["window_start_msc"], "window_start_msc", line)
            eval_ms = _integer(row["evaluation_time_msc"], "evaluation_time_msc", line)
            observations = _integer(row["observations"], "observations", line)
            bid = _number(row["bid"], "bid", line)
            ask = _number(row["ask"], "ask", line)
            _momentum = _number(row["momentum_bps"], "momentum_bps", line)
            volatility = _number(row["realized_volatility_bps"], "realized_volatility_bps", line)
            efficiency = _number(row["efficiency_ratio"], "efficiency_ratio", line)

            if quote_ms <= 0 or window_ms <= 0 or eval_ms <= 0:
                raise DatasetIntegrityError(f"line {line}: timestamps must be positive")
            if not window_ms <= quote_ms <= eval_ms:
                raise DatasetIntegrityError(
                    f"line {line}: require window_start <= quote_time <= evaluation_time"
                )
            if observations < 2:
                raise DatasetIntegrityError(f"line {line}: observations must be at least 2")
            if bid <= 0 or ask <= bid:
                raise DatasetIntegrityError(f"line {line}: bid/ask is invalid or crossed")
            if volatility < 0:
                raise DatasetIntegrityError(f"line {line}: realized volatility cannot be negative")
            if not 0.0 <= efficiency <= 1.0:
                raise DatasetIntegrityError(f"line {line}: efficiency_ratio must be in [0, 1]")

            stream = (source_id, symbol)
            identity = (source_id, symbol, eval_ms)
            if identity in seen:
                raise DatasetIntegrityError(f"line {line}: duplicate source/symbol/evaluation timestamp")
            previous = last_eval.get(stream)
            if previous is not None and eval_ms <= previous:
                raise DatasetIntegrityError(
                    f"line {line}: evaluation timestamps are not strictly increasing "
                    f"for source={source_id!r}, symbol={symbol}"
                )
            seen.add(identity)
            last_eval[stream] = eval_ms
            grouped[stream].append(eval_ms)
            schema_versions.add(schema)
            feature_versions.add(feature)
            rows += 1
    except csv.Error as exc:
        raise DatasetIntegrityError(f"malformed CSV: {exc}") from exc

    if rows == 0:
        raise DatasetIntegrityError("dataset contains a header but no data records")

    streams = []
    for (source_id, symbol), timestamps in sorted(grouped.items()):
        streams.append({
            "source_id": source_id,
            "symbol": symbol,
            "records": len(timestamps),
            "first_evaluation_time_msc": timestamps[0],
            "first_evaluation_utc": _utc(timestamps[0]),
            "last_evaluation_time_msc": timestamps[-1],
            "last_evaluation_utc": _utc(timestamps[-1]),
        })

    return {
        "status": "PASS",
        "dataset": source.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "records": rows,
        "schema_versions": sorted(schema_versions),
        "feature_versions": sorted(feature_versions),
        "streams": streams,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="MT5-exported feature dataset")
    parser.add_argument("--manifest", type=Path, help="optional path to write JSON manifest")
    args = parser.parse_args()
    try:
        manifest = audit_dataset(args.csv_file)
    except (DatasetIntegrityError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    rendered = json.dumps(manifest, indent=2, sort_keys=True)
    print(rendered)
    if args.manifest:
        args.manifest.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
