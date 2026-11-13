import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from tools.mt5_xauusd_candidate_signals import SignalError, generate_candidate_events


def make_features(count=220):
    start = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        # Smooth deterministic drift with periodic impulses to exercise both directions.
        close = 2600.0 * (1.0 + i * 0.00008 + (0.0008 if i % 17 == 0 else 0.0))
        rows.append({
            "window_start_utc": (start + timedelta(seconds=5 * i)).isoformat(),
            "window_seconds": 5,
            "tick_count": 20,
            "observed_span_ms": 4900,
            "ticks_per_second": 4.081633,
            "mid_open": close,
            "mid_high": close + 0.035,
            "mid_low": close - 0.035,
            "mid_close": close,
            "return_bps": 0.3,
            "range_bps": 0.27,
            "realized_volatility_bps": 0.2 + (i % 4) * 0.01,
            "trend_efficiency": 0.7,
            "spread_points_median": 240.0,
            "spread_points_p95": 240.0,
            "spread_points_max": 240.0,
            "max_intertick_gap_ms": 400,
            "gaps_over_1s": 0,
            "mid_price_change_ratio": 1.0,
        })
    return {
        "status": "PASS",
        "research_only": True,
        "feature_schema": "VELTRIX_XAUUSD_TICK_WINDOWS_V1",
        "canonical_symbol": "XAUUSD",
        "source_sha256": "a" * 64,
        "window_seconds": 5,
        "window_count": len(rows),
        "features": rows,
    }


def registry():
    with open("research/xauusd_strategy_registry_v1.json", encoding="utf-8") as handle:
        return json.load(handle)


def test_generates_only_registered_xauusd_candidate_events():
    result = generate_candidate_events(make_features(), registry())
    assert result["status"] == "PASS"
    assert result["research_only"] is True
    assert result["canonical_symbol"] == "XAUUSD"
    assert result["evaluated_windows"] == 220
    assert result["signal_count"] > 0
    assert {event["candidate_id"] for event in result["events"]} <= {
        "XAU_MOMENTUM_CONTINUATION_V1",
        "XAU_MEAN_REVERSION_V1",
        "XAU_VOLATILITY_BREAKOUT_V1",
    }
    assert {event["horizon_seconds"] for event in result["events"]} <= {5, 15, 30, 60}
    assert all(event["execution_sent"] is False for event in result["events"])
    assert len({event["signal_id"] for event in result["events"]}) == result["signal_count"]


def test_signal_generation_is_deterministic():
    features = make_features()
    first = generate_candidate_events(features, registry())
    second = generate_candidate_events(features, registry())
    assert first == second


def test_future_window_mutation_cannot_change_earlier_signals():
    original = make_features()
    mutated = copy.deepcopy(original)
    cutoff = 150
    for row in mutated["features"][cutoff + 1:]:
        row["mid_close"] *= 1.2
        row["mid_high"] *= 1.2
        row["mid_low"] *= 1.2
    first = generate_candidate_events(original, registry())
    second = generate_candidate_events(mutated, registry())
    first_early = [e for e in first["events"] if e["feature_window_start_msc"] <=
                   first["events"][0]["feature_window_start_msc"] + cutoff * 5000]
    second_early = [e for e in second["events"] if e["feature_window_start_msc"] <=
                    second["events"][0]["feature_window_start_msc"] + cutoff * 5000]
    assert first_early == second_early


def test_gap_blocks_events_at_discontinuous_window():
    features = make_features()
    gap_index = 150
    stamp = datetime.fromisoformat(features["features"][gap_index]["window_start_utc"])
    features["features"][gap_index]["window_start_utc"] = (stamp + timedelta(seconds=5)).isoformat()
    features["features"][gap_index + 1:][0]["window_start_utc"] = (
        datetime.fromisoformat(features["features"][gap_index + 1]["window_start_utc"]) + timedelta(seconds=5)
    ).isoformat()
    result = generate_candidate_events(features, registry())
    blocked_end = int((stamp + timedelta(seconds=10)).timestamp() * 1000)
    assert not any(event["signal_window_end_msc"] == blocked_end for event in result["events"])


@pytest.mark.parametrize("mutation", [
    {"canonical_symbol": "XAGUSD"},
    {"feature_schema": "OTHER"},
    {"research_only": False},
    {"source_sha256": "bad"},
    {"window_seconds": 10},
])
def test_rejects_invalid_feature_contract(mutation):
    features = make_features()
    features.update(mutation)
    with pytest.raises(SignalError):
        generate_candidate_events(features, registry())


def test_rejects_naive_feature_timestamps():
    features = make_features()
    features["features"][0]["window_start_utc"] = "2026-11-12T12:00:00"
    with pytest.raises(SignalError, match="timezone"):
        generate_candidate_events(features, registry())


def test_rejects_nonchronological_windows():
    features = make_features()
    features["features"][4]["window_start_utc"] = features["features"][3]["window_start_utc"]
    with pytest.raises(SignalError, match="chronological"):
        generate_candidate_events(features, registry())
