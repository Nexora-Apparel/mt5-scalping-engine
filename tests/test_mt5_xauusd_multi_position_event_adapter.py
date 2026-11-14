import copy
import json
from datetime import datetime, timezone

import pytest

from tools.mt5_xauusd_multi_position_event_adapter import (
    MultiPositionAdapterError,
    build_multi_position_events,
)


def fixture_payloads():
    start = 1_800_000_000_000
    rows = []
    for i in range(20):
        rows.append({
            "window_start_utc": datetime.fromtimestamp(start / 1000 + i * 5, timezone.utc).isoformat(),
            "realized_volatility_bps": 2.0,
            "mid_close": 100.0 + i * 0.01,
        })
    features = {
        "status": "PASS", "research_only": True, "canonical_symbol": "XAUUSD",
        "source_sha256": "a" * 64, "features": rows,
    }
    candidates = {
        "status": "PASS", "research_only": True, "canonical_symbol": "XAUUSD",
        "source_sha256": "a" * 64, "data_role": "DEVELOPMENT_ONLY",
        "events": [
            {"signal_id": "short", "candidate_id": "MOM", "signal_window_index": 10,
             "signal_window_end_msc": start + 11 * 5000, "direction": "long",
             "horizon_seconds": 5, "parameters": {"lookback_seconds": 10}},
            {"signal_id": "long", "candidate_id": "MOM", "signal_window_index": 12,
             "signal_window_end_msc": start + 13 * 5000, "direction": "short",
             "horizon_seconds": 15, "parameters": {"lookback_seconds": 10}},
        ],
    }
    broker = {
        "account_mode": "DEMO", "trading_enabled": False,
        "instrument_specs": {"XAUUSD": {"point_size": 0.01, "tick_size": 0.01, "stops_level_points": 10}},
    }
    policy = {
        "status": "PREREGISTERED_RESEARCH_ONLY", "execution_enabled": False,
        "holding_seconds": [15, 30, 60],
        "stop_volatility_multipliers": [1.0, 2.0],
        "take_profit_reward_r_multiples": [0.5, 1.0],
    }
    return features, candidates, broker, policy


def test_adapter_creates_only_10_to_60_second_adaptive_sl_tp_events():
    features, candidates, broker, policy = fixture_payloads()
    result = build_multi_position_events(features, candidates, broker, policy)
    assert result["event_count"] == 4
    assert result["skipped_legacy_short_horizon_events"] == 1
    assert {event["hold_seconds"] for event in result["events"]} == {15}
    assert all(event["stop_distance_price"] > 0 for event in result["events"])
    assert all(event["take_profit_distance_price"] > 0 for event in result["events"])
    assert all(event["execution_authorized"] is False for event in result["events"])


def test_stop_and_target_distances_are_tick_aligned_and_stop_respects_broker_minimum():
    features, candidates, broker, policy = fixture_payloads()
    result = build_multi_position_events(features, candidates, broker, policy)
    minimum = 10 * 0.01
    for event in result["events"]:
        assert event["stop_distance_price"] >= minimum
        assert round(event["stop_distance_price"] / 0.01) == pytest.approx(event["stop_distance_price"] / 0.01)
        assert round(event["take_profit_distance_price"] / 0.01) == pytest.approx(event["take_profit_distance_price"] / 0.01)


def test_adapter_rejects_feature_candidate_source_hash_mismatch():
    features, candidates, broker, policy = fixture_payloads()
    candidates["source_sha256"] = "b" * 64
    with pytest.raises(MultiPositionAdapterError, match="hashes"):
        build_multi_position_events(features, candidates, broker, policy)


def test_adapter_rejects_non_demo_or_enabled_trading():
    features, candidates, broker, policy = fixture_payloads()
    broker["trading_enabled"] = True
    with pytest.raises(MultiPositionAdapterError, match="DEMO"):
        build_multi_position_events(features, candidates, broker, policy)


def test_future_feature_mutations_do_not_change_prior_only_stop_distance():
    features, candidates, broker, policy = fixture_payloads()
    base = build_multi_position_events(features, candidates, broker, policy)
    mutated = copy.deepcopy(features)
    for row in mutated["features"][13:]:
        row["realized_volatility_bps"] = 1000.0
        row["mid_close"] = 10000.0
    after = build_multi_position_events(mutated, candidates, broker, policy)
    assert [e["stop_distance_price"] for e in base["events"]] == [
        e["stop_distance_price"] for e in after["events"]
    ]
