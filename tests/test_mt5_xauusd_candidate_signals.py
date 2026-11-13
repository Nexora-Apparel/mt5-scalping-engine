import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.mt5_xauusd_candidate_signals import CandidateError, generate_candidate_events


REGISTRY_PATH = Path("research/xauusd_strategy_registry_v1.json")


@pytest.fixture
def registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def make_features(count=100):
    rows = []
    start = 1_800_000_000_000
    for i in range(count):
        mid = 100.0
        rows.append({
            "window_start_utc": datetime.fromtimestamp(start / 1000 + i * 5, timezone.utc).isoformat(),
            "window_seconds": 5,
            "tick_count": 4,
            "observed_span_ms": 4000,
            "ticks_per_second": 1.0,
            "mid_open": mid,
            "mid_high": mid + 0.001,
            "mid_low": mid - 0.001,
            "mid_close": mid,
            "return_bps": 0.0,
            "range_bps": 0.2,
            "realized_volatility_bps": 1.0,
            "trend_efficiency": 0.0,
            "spread_points_median": 240.0,
            "spread_points_p95": 240.0,
            "spread_points_max": 240.0,
            "max_intertick_gap_ms": 100,
            "gaps_over_1s": 0,
            "mid_price_change_ratio": 1.0,
        })
    return {
        "status": "PASS",
        "research_only": True,
        "feature_schema": "VELTRIX_XAUUSD_TICK_WINDOWS_V1",
        "canonical_symbol": "XAUUSD",
        "broker_symbol": "XAUUSDm",
        "source_sha256": "f" * 64,
        "source_records": count * 4,
        "window_seconds": 5,
        "window_count": count,
        "features": rows,
    }


def test_flat_market_produces_no_candidate_events(registry):
    result = generate_candidate_events(make_features(), registry)
    assert result["status"] == "PASS"
    assert result["candidate_event_count"] == 0
    assert result["data_role"] == "UNCLASSIFIED_NOT_HOLDOUT"
    assert result["final_holdout_eligible"] is False


def test_momentum_uses_completed_window_and_prior_volatility(registry):
    features = make_features()
    features["features"][10]["mid_close"] = 100.2
    features["features"][10]["mid_high"] = 100.201
    features["features"][10]["mid_low"] = 100.199
    result = generate_candidate_events(features, registry)
    events = [
        event for event in result["events"]
        if event["candidate_id"] == "XAU_MOMENTUM_CONTINUATION_V1"
        and event["signal_window_index"] == 10
        and event["parameters"]["lookback_seconds"] == 5
    ]
    assert events
    assert all(event["direction"] == "long" for event in events)
    assert {event["horizon_seconds"] for event in events} == {5, 15, 30, 60}
    assert all(event["signal_window_end_msc"] > 0 for event in events)


def test_mean_reversion_direction_is_opposite_displacement(registry):
    features = make_features()
    features["features"][20]["mid_close"] = 99.8
    features["features"][20]["mid_high"] = 99.801
    features["features"][20]["mid_low"] = 99.799
    result = generate_candidate_events(features, registry)
    events = [
        event for event in result["events"]
        if event["candidate_id"] == "XAU_MEAN_REVERSION_V1"
        and event["signal_window_index"] == 20
        and event["parameters"]["lookback_seconds"] == 15
    ]
    assert events
    assert all(event["direction"] == "long" for event in events)


def test_breakout_requires_full_past_compression_history(registry):
    features = make_features(count=70)
    features["features"][66]["mid_close"] = 101.0
    features["features"][66]["mid_high"] = 101.001
    features["features"][66]["mid_low"] = 100.999
    result = generate_candidate_events(features, registry)
    events = [
        event for event in result["events"]
        if event["candidate_id"] == "XAU_VOLATILITY_BREAKOUT_V1"
        and event["signal_window_index"] == 66
        and event["parameters"]["lookback_seconds"] == 30
    ]
    assert events
    assert all(event["direction"] == "long" for event in events)


def test_future_mutations_do_not_change_earlier_events(registry):
    features = make_features()
    features["features"][15]["mid_close"] = 100.2
    features["features"][15]["mid_high"] = 100.201
    features["features"][15]["mid_low"] = 100.199
    baseline = generate_candidate_events(features, registry)
    mutated = copy.deepcopy(features)
    for row in mutated["features"][16:]:
        row["mid_close"] = 130.0
        row["mid_high"] = 130.1
        row["mid_low"] = 129.9
        row["realized_volatility_bps"] = 99.0
    after = generate_candidate_events(mutated, registry)
    cutoff = baseline["events"]
    before_events = [e for e in cutoff if e["signal_window_index"] <= 15]
    after_events = [e for e in after["events"] if e["signal_window_index"] <= 15]
    assert before_events == after_events


def test_missing_prior_volatility_suppresses_signal(registry):
    features = make_features()
    features["features"][9]["realized_volatility_bps"] = None
    features["features"][10]["mid_close"] = 100.2
    features["features"][10]["mid_high"] = 100.201
    features["features"][10]["mid_low"] = 100.199
    result = generate_candidate_events(features, registry)
    assert not [
        event for event in result["events"]
        if event["candidate_id"] == "XAU_MOMENTUM_CONTINUATION_V1"
        and event["signal_window_index"] == 10
        and event["parameters"]["lookback_seconds"] == 5
    ]


@pytest.mark.parametrize("symbol", ["XAGUSD", "BTCUSD", "EURUSD"])
def test_rejects_non_xauusd_feature_data(registry, symbol):
    features = make_features()
    features["canonical_symbol"] = symbol
    with pytest.raises(CandidateError, match="XAUUSD"):
        generate_candidate_events(features, registry)


def test_rejects_source_tick_count_mismatch(registry):
    features = make_features()
    features["source_records"] += 1
    with pytest.raises(CandidateError, match="reconcile"):
        generate_candidate_events(features, registry)


def test_rejects_nonchronological_windows(registry):
    features = make_features()
    features["features"][12]["window_start_utc"] = features["features"][11]["window_start_utc"]
    with pytest.raises(CandidateError, match="strictly chronological"):
        generate_candidate_events(features, registry)


def test_candidate_events_never_contain_execution_or_pnl_fields(registry):
    features = make_features()
    features["features"][10]["mid_close"] = 100.2
    features["features"][10]["mid_high"] = 100.201
    features["features"][10]["mid_low"] = 100.199
    result = generate_candidate_events(features, registry)
    assert result["research_only"] is True
    for event in result["events"]:
        assert event["event_origin"] == "CANDIDATE_RESEARCH_SIGNAL_NOT_TRADE"
        assert event["execution_authorized"] is False
        assert "gross_pnl_price_units" not in event
        assert "net_after_commission" not in event
