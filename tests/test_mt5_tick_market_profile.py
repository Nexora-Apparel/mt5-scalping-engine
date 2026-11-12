import csv
import hashlib
import json
from datetime import datetime, timezone

import pytest

from tools.mt5_tick_market_profile import HEADER, ProfileError, profile_dataset


def row(symbol, stamp, bid=3000.0, ask=3000.2):
    return {
        "schema_version": "1", "source_id": "test-source",
        "canonical_symbol": symbol, "broker_symbol": symbol + "m",
        "time_msc": str(stamp),
        "time_utc": datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).isoformat(),
        "bid": str(bid), "ask": str(ask), "last": str((bid + ask) / 2),
        "volume": "1", "volume_real": "1.0", "flags": "3",
    }


def write_fixture(tmp_path, rows):
    csv_path = tmp_path / "ticks.csv"
    manifest_path = tmp_path / "manifest.json"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    raw = csv_path.read_bytes()
    manifest = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "records": len(rows), "account_mode": "DEMO",
        "trading_enabled": False, "dll_imports_enabled": False,
        "instrument_specs": {
            "XAUUSD": {"point": 0.001, "broker_symbol": "XAUUSDm"},
            "XAGUSD": {"point": 0.001, "broker_symbol": "XAGUSDm"},
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return csv_path, manifest_path


def test_profiles_both_symbols_and_marks_long_silver_gap_for_review(tmp_path):
    base = 1_800_000_000_000
    rows = [
        row("XAUUSD", base), row("XAUUSD", base + 1000), row("XAUUSD", base + 2000),
        row("XAGUSD", base), row("XAGUSD", base + 1000), row("XAGUSD", base + 8000),
    ]
    csv_path, manifest_path = write_fixture(tmp_path, rows)
    result = profile_dataset(csv_path, manifest_path)
    assert result["status"] == "REVIEW"
    assert result["symbols"]["XAUUSD"]["status"] == "PASS"
    assert result["symbols"]["XAGUSD"]["gaps_over_5s"] == 1
    assert result["symbols"]["XAGUSD"]["max_intertick_gap_ms"] == 7000
    assert result["profile_type"] == "OFFLINE_DESCRIPTIVE_ONLY"


def test_rejects_csv_hash_mismatch(tmp_path):
    csv_path, manifest_path = write_fixture(tmp_path, [
        row("XAUUSD", 1_800_000_000_000), row("XAGUSD", 1_800_000_000_000)
    ])
    csv_path.write_text(csv_path.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="SHA-256"):
        profile_dataset(csv_path, manifest_path)



def test_rejects_failed_collector_manifest(tmp_path):
    csv_path, manifest_path = write_fixture(tmp_path, [
        row("XAUUSD", 1_800_000_000_000), row("XAGUSD", 1_800_000_000_000)
    ])
    manifest = json.loads(manifest_path.read_text())
    manifest["status"] = "FAIL"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProfileError, match="overall status"):
        profile_dataset(csv_path, manifest_path)

def test_rejects_non_demo_or_trading_enabled_manifest(tmp_path):
    csv_path, manifest_path = write_fixture(tmp_path, [
        row("XAUUSD", 1_800_000_000_000), row("XAGUSD", 1_800_000_000_000)
    ])
    manifest = json.loads(manifest_path.read_text())
    manifest["trading_enabled"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProfileError, match="trading and DLL"):
        profile_dataset(csv_path, manifest_path)


def test_rejects_duplicate_ticks(tmp_path):
    item = row("XAUUSD", 1_800_000_000_000)
    csv_path, manifest_path = write_fixture(tmp_path, [
        item, item, row("XAGUSD", 1_800_000_000_000)
    ])
    with pytest.raises(ProfileError, match="duplicate"):
        profile_dataset(csv_path, manifest_path)


def test_rejects_timestamp_order_regression(tmp_path):
    csv_path, manifest_path = write_fixture(tmp_path, [
        row("XAUUSD", 1_800_000_000_100),
        row("XAUUSD", 1_800_000_000_000),
        row("XAGUSD", 1_800_000_000_000),
    ])
    with pytest.raises(ProfileError, match="moved backwards"):
        profile_dataset(csv_path, manifest_path)
