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
        {"session_id": "validation_03", "run_id": 43390000003},
        {"session_id": "validation_04", "run_id": 43390000004},
        {"session_id": "validation_05", "run_id": 43390000005},
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



def test_artifact_intake_rejects_incomplete_validation_session_set():
    mapping = {"sessions": [
        {"session_id": "validation_01", "run_id": 43390000001},
        {"session_id": "validation_03", "run_id": 43390000003},
        {"session_id": "validation_04", "run_id": 43390000004},
    ]}
    with pytest.raises(ArtifactIntakeError, match="every eligible validation session together"):
        validate_session_map(mapping, PLAN, stage="validation")

def test_artifact_intake_rejects_explicitly_ineligible_validation_02():
    with pytest.raises(ArtifactIntakeError, match="explicitly ineligible"):
        validate_session_map({"sessions": [{"session_id": "validation_02", "run_id": 43390000002}]}, PLAN, stage="validation")


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
    assert "fetch-depth: 0" in workflow
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
        "collection_started_utc": "2026-11-14T00:01:00Z",
        "collection_ended_utc": "2026-11-14T00:31:02Z",
        "session_id": "validation_01",
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
def test_development_artifact_id_must_match_preregistered_artifact(tmp_path, monkeypatch):
    import tools.prepare_xauusd_walk_forward_catalog as intake

    calls = iter([
        {"status": "completed", "conclusion": "success"},
        {"artifacts": [{"id": 99999999999, "name": "veltrix-exness-demo-ticks-8", "expired": False}]},
    ])
    monkeypatch.setattr(intake, "_gh_json", lambda *args, **kwargs: next(calls))
    with pytest.raises(ArtifactIntakeError, match="artifact ID"):
        intake.download_session_artifacts(
            [{"session_id": "session8", "run_id": 43333365050}],
            PLAN,
            repo="Nexora-Apparel/mt5-scalping-engine",
            workspace=tmp_path,
        )


def test_quote_validation_snapshot_is_verified_and_preserved_in_catalog(tmp_path, monkeypatch):
    import hashlib
    from datetime import datetime, timedelta, timezone
    import tools.prepare_xauusd_walk_forward_catalog as intake

    tick_bytes = b"synthetic-xauusd-demo-ticks-with-quote-snapshot"
    tick_digest = hashlib.sha256(tick_bytes).hexdigest()
    observed = datetime(2026, 11, 14, 0, 1, 0, 500000, tzinfo=timezone.utc)
    quote_time = observed - timedelta(milliseconds=100)
    quote_msc = round(quote_time.timestamp() * 1000)
    quote_csv = (
        "schema_version,canonical_symbol,broker_symbol,observed_at_utc,quote_time_msc,"
        "quote_time_utc,bid,ask,point,spread_points,quote_age_ms\n"
        f"1,XAUUSD,XAUUSDm,{observed.isoformat()},{quote_msc},{quote_time.isoformat()},"
        "2000.000,2000.240,0.001,240,100\n"
    ).encode()
    quote_meta = {
        "filename": "quote_validation_samples.csv",
        "bytes": len(quote_csv),
        "records": 1,
        "sha256": hashlib.sha256(quote_csv).hexdigest(),
    }
    manifest = {
        "sha256": tick_digest,
        "status": "PASS",
        "data_audit_status": "PASS",
        "duration_clock": "monotonic",
        "duration_seconds": 1802.0,
        "collection_started_utc": "2026-11-14T00:01:00Z",
        "collection_ended_utc": "2026-11-14T00:31:02Z",
        "session_id": "validation_01",
        "account_mode": "DEMO",
        "trading_enabled": False,
        "dll_imports_enabled": False,
        "symbols": {"XAUUSD": "XAUUSDm"},
        "instrument_specs": {
            "XAUUSD": {"currency_base": "XAU", "currency_profit": "USD", "point": 0.001}
        },
        "quote_validation_dataset": quote_meta,
    }
    calls = iter([
        {"status": "completed", "conclusion": "success"},
        {"artifacts": [{"name": "veltrix-exness-demo-ticks-101", "expired": False}]},
    ])
    monkeypatch.setattr(intake, "_gh_json", lambda *args, **kwargs: next(calls))

    def fake_run(args, cwd, capture_output, text, check):
        target = Path(args[args.index("--dir") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "veltrix_exness_demo_ticks.csv").write_bytes(tick_bytes)
        (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (target / "quote_validation_samples.csv").write_bytes(quote_csv)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(intake.subprocess, "run", fake_run)
    result = intake.download_session_artifacts(
        [{"session_id": "validation_01", "run_id": 43390000101}],
        PLAN,
        repo="Nexora-Apparel/mt5-scalping-engine",
        workspace=tmp_path,
    )
    catalog = json.loads(result["catalog_path"].read_text(encoding="utf-8"))
    quote_relative = catalog["sessions"][0]["quote_validation_csv"]
    retained = tmp_path / "research" / quote_relative
    assert retained.read_bytes() == quote_csv
    assert catalog["sessions"][0]["session_id"] == "validation_01"


def test_quote_validation_snapshot_hash_mismatch_fails_closed(tmp_path):
    import tools.prepare_xauusd_walk_forward_catalog as intake

    quote_path = tmp_path / "quote_validation_samples.csv"
    quote_path.write_text(
        "canonical_symbol,broker_symbol,observed_at_utc,quote_time_msc,quote_time_utc,"
        "bid,ask,point,spread_points,quote_age_ms\n",
        encoding="utf-8",
    )
    manifest = {
        "symbols": {"XAUUSD": "XAUUSDm"},
        "quote_validation_dataset": {
            "filename": quote_path.name,
            "bytes": quote_path.stat().st_size,
            "records": 1,
            "sha256": "0" * 64,
        },
    }
    with pytest.raises(ArtifactIntakeError, match="SHA-256"):
        intake._validate_quote_snapshot(manifest, tmp_path)


def test_validation_workflow_default_contains_all_four_eligible_sessions():
    workflow = (ROOT / ".github/workflows/xauusd-walk-forward-validation.yml").read_text(encoding="utf-8")
    for run_id in (43408593546, 43773683398, 43814840356, 44096443341):
        assert str(run_id) in workflow
