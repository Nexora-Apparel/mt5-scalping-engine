import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from tools.mt5_multi_session_certification import certify_sessions
from tools.mt5_tick_market_profile import HEADER, ProfileError


def make_session(tmp_path, name, start_ms, *, gap_ms=1000):
    csv_path = tmp_path / f"{name}.csv"
    manifest_path = tmp_path / f"{name}.json"
    rows = []
    for symbol in ("XAUUSD", "XAGUSD"):
        for offset in (0, gap_ms, gap_ms * 2):
            stamp = start_ms + offset
            rows.append({
                "schema_version": "1", "source_id": name,
                "canonical_symbol": symbol, "broker_symbol": symbol + "m",
                "time_msc": str(stamp),
                "time_utc": datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat(),
                "bid": "3000.0", "ask": "3000.2", "last": "3000.1",
                "volume": "1", "volume_real": "1.0", "flags": "3",
            })
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rows)
    start = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    end = start + timedelta(seconds=1800, milliseconds=50)
    raw = csv_path.read_bytes()
    manifest = {
        "sha256": hashlib.sha256(raw).hexdigest(), "records": len(rows),
        "account_mode": "DEMO", "status": "PASS",
        "trading_enabled": False, "dll_imports_enabled": False,
        "duration_clock": "monotonic", "duration_seconds": 1800.05,
        "collection_started_utc": start.isoformat(),
        "collection_ended_utc": end.isoformat(),
        "instrument_specs": {
            "XAUUSD": {"point": 0.001, "broker_symbol": "XAUUSDm"},
            "XAGUSD": {"point": 0.001, "broker_symbol": "XAGUSDm"},
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return csv_path, manifest_path


def test_requires_two_sessions(tmp_path):
    one = make_session(tmp_path, "one", 1_800_000_000_000)
    with pytest.raises(ProfileError, match="at least two"):
        certify_sessions([one])


def test_aggregates_independent_sessions_without_execution_claims(tmp_path):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    second = make_session(tmp_path, "two", 1_800_003_000_000)
    result = certify_sessions([first, second])
    assert result["status"] == "PASS"
    assert result["certification_type"] == "MULTI_SESSION_DESCRIPTIVE_ONLY"
    assert result["session_count"] == 2
    assert result["symbols"]["XAUUSD"]["sessions"] == 2
    assert result["symbols"]["XAGUSD"]["total_records"] == 6
    assert any("does not certify" in item for item in result["limitations"])


def test_rejects_duplicate_dataset(tmp_path):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    with pytest.raises(ProfileError, match="duplicate dataset"):
        certify_sessions([first, first])


def test_rejects_overlapping_collection_intervals(tmp_path):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    # Starts 10 minutes after the first session, so the 30-minute windows overlap.
    second = make_session(tmp_path, "two", 1_800_000_600_000)
    with pytest.raises(ProfileError, match="overlapping collection intervals"):
        certify_sessions([first, second])


@pytest.mark.parametrize("duration", [None, "1800", True, float("nan"), float("inf"), -1, 1799.99])
def test_rejects_invalid_or_short_duration_evidence(tmp_path, duration):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    second = make_session(tmp_path, "two", 1_800_003_000_000)
    manifest = json.loads(second[1].read_text())
    manifest["duration_seconds"] = duration
    second[1].write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProfileError):
        certify_sessions([first, second])


def test_rejects_non_monotonic_duration_clock(tmp_path):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    second = make_session(tmp_path, "two", 1_800_003_000_000)
    manifest = json.loads(second[1].read_text())
    manifest["duration_clock"] = "wall"
    second[1].write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProfileError, match="not measured monotonically"):
        certify_sessions([first, second])


def test_rejects_non_increasing_utc_interval(tmp_path):
    first = make_session(tmp_path, "one", 1_800_000_000_000)
    second = make_session(tmp_path, "two", 1_800_003_000_000)
    manifest = json.loads(second[1].read_text())
    manifest["collection_ended_utc"] = manifest["collection_started_utc"]
    second[1].write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProfileError, match="end must follow start"):
        certify_sessions([first, second])
