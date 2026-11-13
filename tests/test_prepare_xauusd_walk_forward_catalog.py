import json
from pathlib import Path

import pytest

from tools.prepare_xauusd_walk_forward_catalog import ArtifactIntakeError, validate_session_map

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "research/xauusd_walk_forward_plan_v1.json").read_text(encoding="utf-8"))


def test_artifact_intake_accepts_only_preregistered_development_and_validation_ids():
    mapping = {"sessions": [
        {"session_id": "session8", "run_id": 43333365050},
        {"session_id": "session9", "run_id": 43338046880},
        {"session_id": "validation_01", "run_id": 43390000001},
    ]}
    result = validate_session_map(mapping, PLAN, stage="validation")
    assert result == mapping["sessions"]


@pytest.mark.parametrize("item", [
    {"session_id": "holdout_01", "run_id": 43390000001},
    {"session_id": "XAGUSD", "run_id": 43390000001},
    {"session_id": "validation_01", "run_id": True},
    {"session_id": "validation_99", "run_id": 43390000001},
])
def test_artifact_intake_rejects_unregistered_sessions_and_invalid_run_ids(item):
    with pytest.raises(ArtifactIntakeError):
        validate_session_map({"sessions": [item]}, PLAN, stage="validation")


def test_artifact_intake_rejects_duplicate_session_ids():
    mapping = {"sessions": [
        {"session_id": "validation_01", "run_id": 43390000001},
        {"session_id": "validation_01", "run_id": 43390000002},
    ]}
    with pytest.raises(ArtifactIntakeError, match="duplicate"):
        validate_session_map(mapping, PLAN, stage="validation")


def test_artifact_intake_cannot_open_holdout_partition():
    with pytest.raises(ArtifactIntakeError, match="sealed"):
        validate_session_map({"sessions": []}, PLAN, stage="holdout")
def test_phase8_intake_workflow_is_manual_read_only_and_validation_only():
    workflow = (ROOT / ".github/workflows/xauusd-walk-forward-validation.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "permissions:" in workflow and "actions: read" in workflow and "contents: read" in workflow
    assert "--stage validation" in workflow
    assert "veltrix-xauusd-walk-forward-validation" in workflow
    assert "XAGUSD" not in workflow
    assert "OrderSend(" not in workflow
