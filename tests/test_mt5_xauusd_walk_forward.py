import json
from pathlib import Path

import pytest

from tools.mt5_xauusd_walk_forward import (
    WalkForwardError,
    _validate_selected_configurations,
    assess_session_catalog,
    run_walk_forward,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "research/xauusd_walk_forward_plan_v1.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((ROOT / "research/xauusd_strategy_registry_v1.json").read_text(encoding="utf-8"))


def test_preregistered_plan_matches_exact_development_hashes_and_frozen_registry():
    result = validate_plan(PLAN, REGISTRY)
    assert result["status"] == "PASS"
    assert result["development_session_ids"] == ["session8", "session9"]
    assert len(result["validation_session_ids"]) == 4
    assert len(result["final_holdout_session_ids"]) == 10
    assert result["commission_status"] == "UNVERIFIED_REQUIRED_INPUT"
    assert result["net_performance_allowed"] is False


def test_plan_rejects_promoting_development_data_to_holdout():
    changed = json.loads(json.dumps(PLAN))
    changed["development_sessions"][0]["expected_sha256"] = "0" * 64
    with pytest.raises(WalkForwardError, match="development session hashes"):
        validate_plan(changed, REGISTRY)


def test_validation_stage_blocks_until_all_future_validation_sessions_exist():
    catalog = {
        "sessions": [
            {"session_id": "session8", "csv": "session8.csv", "manifest": "session8.json"},
            {"session_id": "session9", "csv": "session9.csv", "manifest": "session9.json"},
        ]
    }
    result = assess_session_catalog(
        PLAN, REGISTRY, catalog, stage="validation", base_dir=ROOT
    )
    assert result["status"] == "BLOCKED_INSUFFICIENT_DATA"
    assert result["missing_session_ids"] == PLAN["validation_sessions"]
    assert result["candidate_scoring_performed"] is False
    assert result["net_performance_allowed"] is False


def test_validation_stage_refuses_to_open_final_holdout_sessions():
    catalog = {"sessions": [
        {"session_id": "holdout_01", "csv": "holdout.csv", "manifest": "holdout.json"}
    ]}
    with pytest.raises(WalkForwardError, match="outside the requested stage"):
        assess_session_catalog(
            PLAN, REGISTRY, catalog, stage="validation", base_dir=ROOT
        )


def test_holdout_stage_requires_validation_selection_freeze_and_complete_partitions():
    result = run_walk_forward(
        PLAN, REGISTRY, {"sessions": []}, stage="holdout", base_dir=ROOT
    )
    assert result["status"] == "BLOCKED_INSUFFICIENT_DATA"
    assert result["candidate_scoring_performed"] is False
    assert "validation_01" in result["missing_session_ids"]
    assert "holdout_01" in result["missing_session_ids"]


def test_selection_freeze_accepts_only_registered_candidate_parameter_combinations():
    selected = [{
        "candidate_id": "XAU_MOMENTUM_CONTINUATION_V1",
        "parameters": {
            "lookback_seconds": 5,
            "standardized_impulse_threshold": 1.0,
        },
        "horizon_seconds": 15,
    }]
    assert _validate_selected_configurations(selected, REGISTRY) == selected
    invalid = json.loads(json.dumps(selected))
    invalid[0]["parameters"]["lookback_seconds"] = 7
    with pytest.raises(WalkForwardError, match="finite grid"):
        _validate_selected_configurations(invalid, REGISTRY)


def test_walk_forward_tool_is_research_only_and_has_no_order_api_calls():
    source = (ROOT / "tools/mt5_xauusd_walk_forward.py").read_text(encoding="utf-8").lower()
    for forbidden in ("ordersend(", "ordersendasync(", "positionopen(", "ctrade", "trade_action_deal"):
        assert forbidden not in source
    assert "final_holdout" in source
    assert "session_clustered_mean_ci_95" in source
    assert "net_after_commission" in source
