from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

from tools.mt5_historical_batch_backfill import validate_interval_plan
from tools.mt5_demo_tick_collector import DiagnosticFailure


def _interval(day: int, start: str = "10:00:00.000", end: str = "10:30:00.000", ident: str | None = None):
    date = f"2026-10-{day:02d}"
    return {"id": ident or f"day_{day}", "from_utc": f"{date}T{start}Z", "to_utc": f"{date}T{end}Z"}


def test_accepts_multiple_distinct_utc_dates_and_sorts_them():
    plan = validate_interval_plan(json.dumps([_interval(14), _interval(12)]))
    assert [item["utc_date"] for item in plan] == ["2026-10-12", "2026-10-14"]
    assert all(item["duration_milliseconds"] == 1_800_000 for item in plan)


@pytest.mark.parametrize("raw", [
    "not-json",
    json.dumps([]),
    json.dumps([_interval(day) for day in range(1, 14)]),
    json.dumps([_interval(12), _interval(12, ident="duplicate")]),
    json.dumps([_interval(12, start="10:00:00.001", end="10:32:00.001")]),
    json.dumps([{"id": "../escape", "from_utc": "2026-10-12T10:00:00Z", "to_utc": "2026-10-12T10:01:00Z"}]),
    json.dumps([{"id": "x", "from_utc": "2026-10-12T10:00:00", "to_utc": "2026-10-12T10:01:00"}]),
])
def test_rejects_invalid_or_unsafe_plans(raw):
    with pytest.raises((DiagnosticFailure, ValueError)):
        validate_interval_plan(raw)


def test_rejects_total_duration_above_six_hours():
    plan = [_interval(day, "10:00:00.000", "10:31:00.000") for day in range(1, 13)]
    with pytest.raises(DiagnosticFailure, match="six-hour"):
        validate_interval_plan(json.dumps(plan))


def test_batch_workflow_requires_independently_pinned_exness_installer_signer():
    workflow = (ROOT / ".github/workflows/xauusd-historical-tick-batch.yml").read_text(encoding="utf-8")
    assert "EXNESS_MT5_SIGNER_THUMBPRINT" in workflow
    assert "independently confirmed" in workflow
    assert "$thumbprint.ToUpperInvariant() -ne $expectedThumbprint" in workflow
    assert "Get-AuthenticodeSignature" in workflow
    assert "AllowLiveTrading=0" in workflow
    assert "AllowDllImport=0" in workflow


def test_preregistered_feasibility_plan_is_bounded_and_not_holdout():
    plan = json.loads((ROOT / "research/xauusd_historical_replay_feasibility_v1.json").read_text(encoding="utf-8"))
    intervals = validate_interval_plan(json.dumps(plan["intervals"]))
    assert plan["status"] == "PREREGISTERED_EXPLORATORY_ONLY"
    assert plan["eligible_for_v1_validation"] is False
    assert plan["eligible_for_v1_holdout"] is False
    assert plan["eligible_for_candidate_approval"] is False
    assert len(intervals) == 4
    assert len({item["utc_date"] for item in intervals}) == 4
    assert sum(item["duration_milliseconds"] for item in intervals) == 7_200_000



def test_batch_continues_after_one_interval_fails(monkeypatch, tmp_path):
    from tools import mt5_historical_batch_backfill as batch

    monkeypatch.setenv("VELTRIX_SOURCE_REF", "reviewed-test-ref")
    monkeypatch.setenv("VELTRIX_SOURCE_COMMIT", "a" * 40)
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("MT5_INSTALLER_SIGNER_THUMBPRINT", "c" * 40)
    calls = []

    def fake_probe(_mt5, start, end, output_dir):
        calls.append(output_dir.name)
        if output_dir.name == "day_12":
            raise DiagnosticFailure("no historical ticks returned for requested interval")
        return {
            "status": "PASS",
            "records": 17,
            "first_tick_utc": "2026-10-14T10:00:00.000Z",
            "last_tick_utc": "2026-10-14T10:30:00.000Z",
            "broker_symbol": "XAUUSDm",
            "account_mode": "DEMO",
            "sha256": "d" * 64,
            "dataset_audit": {"status": "PASS"},
        }

    monkeypatch.setattr(batch, "probe", fake_probe)
    intervals = validate_interval_plan(json.dumps([_interval(12), _interval(14)]))
    result = batch.run_batch(object(), intervals, tmp_path)

    assert calls == ["day_12", "day_14"]
    assert result["status"] == "PARTIAL"
    assert result["attempted_count"] == 2
    assert result["successful_count"] == 1
    assert result["failed_count"] == 1
    assert result["intervals"][0]["error"].endswith("no historical ticks returned for requested interval")
    assert result["intervals"][1]["records"] == 17
    saved = json.loads((tmp_path / "batch_manifest.json").read_text(encoding="utf-8"))
    assert saved["status"] == "PARTIAL"
    assert saved["attempted_count"] == 2
