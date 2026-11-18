from __future__ import annotations

import json
import pytest

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
