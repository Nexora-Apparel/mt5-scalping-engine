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
    {"session_id": "session8", "run_id": 43333365051},
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
def test_artifact_download_builds_catalog_from_verified_xauusd_artifact(tmp_path, monkeypatch):
    import tools.prepare_xauusd_walk_forward_catalog as intake

    csv_bytes = b"synthetic-xauusd-demo-ticks"
    digest = "a" * 64
    manifest = {
        "sha256": digest,
        "status": "PASS",
        "data_audit_status": "PASS",
        "duration_clock": "monotonic",
        "duration_seconds": 1802.0,
        "account_mode": "DEMO",
        "trading_enabled": False,
        "dll_imports_enabled": False,
        "symbols": {"XAUUSD": "XAUUSDm"},
        "instrument_specs": {
            "XAUUSD": {"currency_base": "XAU", "currency_profit": "USD", "point": 0.001}
        },
    }
    calls = iter([
        {"status": "completed", "conclusion": "success"},
        {"artifacts": [{"name": "veltrix-exness-demo-ticks-101", "expired": False}]},
    ])
    monkeypatch.setattr(intake, "_gh_json", lambda *args, **kwargs: next(calls))
    monkeypatch.setattr(intake, "_sha256", lambda path: digest)

    def fake_run(args, cwd, capture_output, text, check):
        target = Path(args[args.index("--dir") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "veltrix_exness_demo_ticks.csv").write_bytes(csv_bytes)
        (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(intake.subprocess, "run", fake_run)
    mapping = [{"session_id": "validation_01", "run_id": 43390000101}]
    result = intake.download_session_artifacts(
        mapping, PLAN, repo="Nexora-Apparel/mt5-scalping-engine", workspace=tmp_path
    )
    catalog = json.loads(result["catalog_path"].read_text(encoding="utf-8"))
    assert result["sessions_downloaded"] == 1
    assert catalog["sessions"][0]["session_id"] == "validation_01"
    assert (tmp_path / "research/xauusd_sessions/validation_01/manifest.json").exists()
    assert (tmp_path / "research/xauusd_sessions/validation_01/veltrix_exness_demo_ticks.csv").exists()
