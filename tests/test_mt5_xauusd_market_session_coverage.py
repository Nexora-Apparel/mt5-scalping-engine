import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.mt5_xauusd_market_session_coverage import (
    SessionCoverageError,
    build_report,
)


def make_source(tmp_path: Path, stamps: list[str]):
    csv_path = tmp_path / "ticks.csv"
    rows = []
    for stamp in stamps:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        rows.append({
            "canonical_symbol": "XAUUSD",
            "time_msc": str(int(dt.timestamp() * 1000)),
            "time_utc": dt.isoformat(),
        })
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical_symbol", "time_msc", "time_utc"])
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = {
        "session_id": "validation_supplemental_test",
        "canonical_symbol": "XAUUSD",
        "status": "PASS",
        "data_audit_status": "PASS",
        "collection_started_utc": "2026-11-16T00:00:00Z",
        "collection_ended_utc": "2026-11-16T23:00:00Z",
        "duration_seconds": 82800,
        "sha256": digest,
    }
    return manifest, csv_path


def test_classifies_asian_london_new_york_and_overlap_with_november_dst_offsets(tmp_path):
    manifest, csv_path = make_source(tmp_path, [
        "2026-11-16T07:30:00Z",  # Tokyo daytime only
        "2026-11-16T09:00:00Z",  # London
        "2026-11-16T13:30:00Z",  # London and New York overlap
        "2026-11-16T20:00:00Z",  # New York
    ])
    report = build_report(manifest, csv_path)
    coverage = report["session_coverage"]
    assert coverage["asian"]["tick_count"] == 1
    assert coverage["london"]["tick_count"] == 2
    assert coverage["new_york"]["tick_count"] == 2
    assert coverage["london_new_york_overlap"]["tick_count"] == 1
    assert coverage["london_new_york_overlap"]["window_intersection_seconds"] == 14400
    assert report["research_only"] is True


def test_overlap_tracks_uk_and_us_dst_mismatch(tmp_path):
    manifest, csv_path = make_source(tmp_path, ["2026-11-16T13:30:00Z"])
    manifest["collection_started_utc"] = "2026-03-29T00:00:00Z"
    manifest["collection_ended_utc"] = "2026-03-29T23:00:00Z"
    manifest["duration_seconds"] = 82800
    # Replace the sample tick with one inside the DST-mismatch overlap (12:00-16:00 UTC).
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical_symbol", "time_msc", "time_utc"])
        writer.writeheader()
        dt = datetime.fromisoformat("2026-03-29T13:30:00+00:00")
        writer.writerow({"canonical_symbol": "XAUUSD", "time_msc": str(int(dt.timestamp()*1000)), "time_utc": dt.isoformat()})
    manifest["sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    report = build_report(manifest, csv_path)
    assert report["session_coverage"]["london_new_york_overlap"]["window_intersection_seconds"] == 14400
    assert report["session_coverage"]["london_new_york_overlap"]["tick_count"] == 1


def test_rejects_source_hash_mismatch(tmp_path):
    manifest, csv_path = make_source(tmp_path, ["2026-11-16T13:30:00Z"])
    manifest["sha256"] = "0" * 64
    with pytest.raises(SessionCoverageError, match="SHA-256"):
        build_report(manifest, csv_path)


def test_rejects_naive_manifest_timestamp(tmp_path):
    manifest, csv_path = make_source(tmp_path, ["2026-11-16T13:30:00Z"])
    manifest["collection_started_utc"] = "2026-11-16T00:00:00"
    with pytest.raises(SessionCoverageError, match="UTC offset"):
        build_report(manifest, csv_path)


def test_rejects_non_monotonic_ticks(tmp_path):
    manifest, csv_path = make_source(tmp_path, [
        "2026-11-16T13:31:00Z",
        "2026-11-16T13:30:00Z",
    ])
    with pytest.raises(SessionCoverageError, match="monotonic"):
        build_report(manifest, csv_path)


def test_rejects_mismatched_epoch_and_iso_timestamp(tmp_path):
    manifest, csv_path = make_source(tmp_path, ["2026-11-16T13:30:00Z"])
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[0]["time_msc"] = str(int(rows[0]["time_msc"]) + 1000)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    manifest["sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    with pytest.raises(SessionCoverageError, match="disagree"):
        build_report(manifest, csv_path)
