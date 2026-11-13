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


def test_holdout_stage_stays_sealed_until_commission_is_verified():
    result = run_walk_forward(
        PLAN, REGISTRY, {"sessions": []}, stage="holdout", base_dir=ROOT
    )
    assert result["status"] == "BLOCKED_COMMISSION_UNVERIFIED"
    assert result["candidate_scoring_performed"] is False
    assert result["holdout_opened"] is False
    assert result["net_performance_allowed"] is False


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

def test_repository_catalog_template_produces_a_blocked_validation_report():
    catalog = json.loads(
        (ROOT / "research/xauusd_walk_forward_catalog_template.json").read_text(encoding="utf-8")
    )
    result = run_walk_forward(PLAN, REGISTRY, catalog, stage="validation", base_dir=ROOT)
    assert result["status"] == "BLOCKED_INSUFFICIENT_DATA"
    assert result["candidate_scoring_performed"] is False
    assert len(result["missing_session_ids"]) == 6


def test_validation_evaluator_aggregates_candidate_and_directional_benchmarks(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import tools.mt5_xauusd_walk_forward as wf

    development = {item["session_id"]: item["expected_sha256"] for item in PLAN["development_sessions"]}
    session_ids = list(development) + list(PLAN["validation_sessions"])
    catalog_items = []
    manifests = {}
    hashes = {}
    base = datetime(2026, 11, 13, tzinfo=timezone.utc)
    for index, sid in enumerate(session_ids):
        start = base + timedelta(days=index)
        end = start + timedelta(minutes=30)
        csv_path = tmp_path / f"{sid}.csv"
        manifest_path = tmp_path / f"{sid}.json"
        csv_path.write_text("synthetic fixture only", encoding="utf-8")
        manifest = {
            "account_mode": "DEMO",
            "trading_enabled": False,
            "dll_imports_enabled": False,
            "instrument_specs": {
                "XAUUSD": {
                    "broker_symbol": "XAUUSDm",
                    "currency_base": "XAU",
                    "currency_profit": "USD",
                    "point": 0.001,
                }
            },
            "collection_started_utc": start.isoformat(),
            "collection_ended_utc": end.isoformat(),
            "duration_seconds": 1800.0,
            "duration_clock": "monotonic",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        catalog_items.append({"session_id": sid, "csv": csv_path.name, "manifest": manifest_path.name})
        manifests[sid] = manifest
        hashes[sid] = development.get(sid, f"{index + 1:064x}")

    monkeypatch.setattr(wf, "profile_dataset", lambda csv, manifest: {
        "status": "PASS", "sha256": hashes[Path(manifest).stem], "records": 100
    })
    features = {
        "features": [
            {"window_start_utc": "2026-11-14T00:00:00+00:00"},
            {"window_start_utc": "2026-11-14T00:00:05+00:00"},
            {"window_start_utc": "2026-11-14T00:00:10+00:00"},
        ]
    }
    monkeypatch.setattr(wf, "build_features", lambda *args, **kwargs: features)
    candidate_event = {
        "signal_id": "candidate-1",
        "candidate_id": "XAU_MOMENTUM_CONTINUATION_V1",
        "parameters": {"lookback_seconds": 5, "standardized_impulse_threshold": 1},
        "horizon_seconds": 5,
        "signal_window_end_msc": 6000,
        "direction": "long",
    }
    monkeypatch.setattr(wf, "generate_candidate_events", lambda *args, **kwargs: {"events": [candidate_event]})
    monkeypatch.setattr(wf, "load_verified_ticks", lambda *args, **kwargs: ([], {}))

    def outcome(event):
        return {
            "signal_id": event["signal_id"],
            "signal_window_end_msc": event["signal_window_end_msc"],
            "status": "OUTCOME_AVAILABLE",
            "entry_time_msc": event["signal_window_end_msc"] + 1,
            "exit_time_msc": event["signal_window_end_msc"] + 5001,
            "slippage_sensitivity": [
                {
                    "slippage_points_per_side": points,
                    "return_before_commission_bps": 10.0 - points,
                }
                for points in [0, 1, 2, 5]
            ],
        }

    monkeypatch.setattr(wf, "replay_events", lambda ticks, events, manifest, registry, source_profile=None: {
        "outcomes": [outcome(event) for event in events]
    })
    monkeypatch.setattr(wf, "evaluate_event", lambda ticks, event, **kwargs: outcome(event))

    ready = wf.assess_session_catalog(
        PLAN, REGISTRY, {"sessions": catalog_items}, stage="validation", base_dir=tmp_path
    )
    assert ready["status"] == "READY_FOR_RESEARCH_EVALUATION"
    report = wf.evaluate_partition(ready, REGISTRY)
    assert report["status"] == "RESEARCH_EVALUATION_COMPLETE"
    assert len(report["candidate_results"]) == 1
    candidate = report["candidate_results"][0]
    assert candidate["aggregate_cost_sensitivity"]["0"]["outcomes"] == 4
    assert candidate["aggregate_cost_sensitivity"]["5"]["mean_return_before_commission_bps"] == 5.0
    assert len(report["benchmarks"]) == 8
    assert report["net_performance_allowed"] is False
    assert report["candidate_approval"] == "NOT_APPROVED"
