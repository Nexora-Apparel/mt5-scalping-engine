import copy
from datetime import datetime, timezone
import pytest
from tools.mt5_xauusd_feature_diagnostics import DiagnosticsError, diagnose_sessions


def make_session(start_ms, source_id, width=5):
    rows = []
    for i in range(40):
        rows.append({
            "window_start_utc": datetime.fromtimestamp((start_ms // (width * 1000) + i) * width, timezone.utc).isoformat(),
            "window_seconds": width,
            "tick_count": 4 + (i % 5),
            "ticks_per_second": 1.0 + (i % 7) / 3,
            "return_bps": 0.000001 + ((i % 9) - 4) / 10,
            "range_bps": 0.2 + (i % 6) / 10,
            "realized_volatility_bps": 0.1 + (i % 8) / 10,
            "trend_efficiency": (i % 10) / 10,
            "spread_points_median": 240.0,
            "spread_points_p95": 240.0,
            "spread_points_max": 240.0,
            "max_intertick_gap_ms": 100 + (i % 4) * 50,
            "gaps_over_1s": i % 3,
            "mid_price_change_ratio": (i % 5) / 4,
        })
    return {
        "status": "PASS",
        "research_only": True,
        "feature_schema": "VELTRIX_XAUUSD_TICK_WINDOWS_V1",
        "canonical_symbol": "XAUUSD",
        "source_sha256": (source_id * 64)[:64],
        "source_records": sum(row["tick_count"] for row in rows),
        "window_seconds": width,
        "window_count": len(rows),
        "features": rows,
    }


def test_diagnoses_two_independent_non_overlapping_sessions():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_300_000, "b")
    result = diagnose_sessions([second, first])
    assert result["status"] == "PASS"
    assert result["research_only"] is True
    assert result["session_count"] == 2
    assert result["total_windows"] == 80
    assert result["sessions"][0]["source_sha256"] == first["source_sha256"]
    assert result["cross_session_median_comparison"]["spread_points_median"]["relative_median_deltas_pct_from_session_1"] == [0.0, 0.0]
    assert result["cross_session_median_comparison"]["return_bps"]["relative_median_deltas_pct_from_session_1"] == [None, None]


def test_rejects_duplicate_source_hashes():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_300_000, "a")
    with pytest.raises(DiagnosticsError, match="unique"):
        diagnose_sessions([first, second])


def test_rejects_overlapping_sessions():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_100_000, "b")
    with pytest.raises(DiagnosticsError, match="overlap"):
        diagnose_sessions([first, second])


def test_rejects_source_tick_count_mismatch():
    first = make_session(1_800_000_000_000, "a")
    first["source_records"] += 1
    second = make_session(1_800_000_300_000, "b")
    with pytest.raises(DiagnosticsError, match="reconcile"):
        diagnose_sessions([first, second])


def test_rejects_different_window_widths():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_300_000, "b", width=10)
    with pytest.raises(DiagnosticsError, match="same feature window"):
        diagnose_sessions([first, second])


def test_zero_variance_correlations_are_null():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_300_000, "b")
    result = diagnose_sessions([first, second])
    assert result["sessions"][0]["pearson_correlations"]["spread_points_median"]["spread_points_median"] is None


def test_rejects_non_xauusd_input():
    first = make_session(1_800_000_000_000, "a")
    second = make_session(1_800_000_300_000, "b")
    first["canonical_symbol"] = "XAGUSD"
    with pytest.raises(DiagnosticsError, match="XAUUSD"):
        diagnose_sessions([first, second])
