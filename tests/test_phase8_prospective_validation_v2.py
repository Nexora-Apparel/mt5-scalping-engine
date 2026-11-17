import json
from pathlib import Path

import pytest

from tools.prepare_xauusd_walk_forward_catalog import ArtifactIntakeError, validate_session_map

ROOT = Path(__file__).resolve().parents[1]
PLAN_V1 = json.loads((ROOT / "research/xauusd_walk_forward_plan_v1.json").read_text(encoding="utf-8"))
PLAN_V2 = json.loads((ROOT / "research/xauusd_walk_forward_plan_v2.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((ROOT / "research/xauusd_strategy_registry_v1.json").read_text(encoding="utf-8"))


def _complete_v2_map():
    return {"sessions": [
        {"session_id": "session8", "run_id": 43333365050},
        {"session_id": "session9", "run_id": 43338046880},
        {"session_id": "validation_01", "run_id": 43408593546},
        {"session_id": "validation_03", "run_id": 43773683398},
        {"session_id": "validation_04", "run_id": 43814840356},
        {"session_id": "validation_05", "run_id": 44096443341},
        *[
            {"session_id": f"validation_{i:02d}", "run_id": 45000000000 + i}
            for i in range(6, 14)
        ],
    ]}


def test_v2_extends_validation_dates_without_mutating_v1_or_candidate_registry():
    assert PLAN_V1["validation_sessions"] == [
        "validation_01", "validation_03", "validation_04", "validation_05"
    ]
    assert PLAN_V2["validation_sessions"] == [
        "validation_01", "validation_03", "validation_04", "validation_05",
        "validation_06", "validation_07", "validation_08", "validation_09",
        "validation_10", "validation_11", "validation_12", "validation_13",
    ]
    assert PLAN_V2["plan_version"] == 2
    assert PLAN_V2["collection_requirements"]["minimum_validation_distinct_dates"] == 12
    assert PLAN_V2["evaluation"] == PLAN_V1["evaluation"]
    assert PLAN_V2["evaluation"]["commission_status"] == "UNVERIFIED_REQUIRED_INPUT"
    assert PLAN_V2["evaluation"]["net_performance_allowed"] is False
    assert REGISTRY["research_only"] is True
    assert REGISTRY["order_execution_enabled"] is False


def test_v2_intake_accepts_only_complete_preregistered_session_map():
    mapping = _complete_v2_map()
    assert validate_session_map(mapping, PLAN_V2, stage="validation") == mapping["sessions"]


def test_v2_intake_rejects_map_missing_any_new_prospective_date():
    mapping = _complete_v2_map()
    mapping["sessions"] = [
        item for item in mapping["sessions"] if item["session_id"] != "validation_13"
    ]
    with pytest.raises(ArtifactIntakeError, match="every eligible validation session together"):
        validate_session_map(mapping, PLAN_V2, stage="validation")


def test_v2_intake_rejects_duplicate_utc_session_id():
    mapping = _complete_v2_map()
    mapping["sessions"].append({"session_id": "validation_06", "run_id": 45000000014})
    with pytest.raises(ArtifactIntakeError, match="duplicate session ID"):
        validate_session_map(mapping, PLAN_V2, stage="validation")


def test_prospective_collection_workflow_exposes_only_preregistered_v2_ids():
    workflow = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8")
    for sid in [f"validation_{i:02d}" for i in range(6, 14)]:
        assert f"- {sid}" in workflow
    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow


def test_v2_validation_workflow_uses_separate_plan_and_artifact_name():
    workflow = (ROOT / ".github/workflows/xauusd-prospective-validation-v2.yml").read_text(encoding="utf-8")
    assert "--plan research/xauusd_walk_forward_plan_v2.json" in workflow
    assert "--stage validation" in workflow
    assert "veltrix-xauusd-walk-forward-validation-v2" in workflow
    assert "schedule:" not in workflow
    assert "permissions:" in workflow and "actions: read" in workflow and "contents: read" in workflow
