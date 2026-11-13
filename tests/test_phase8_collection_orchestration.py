from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase8_collection_is_manual_only_and_session_id_bound():
    source = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "validation_session_id:" in source
    for session_id in ("validation_01", "validation_03", "validation_04", "validation_05"):
        assert session_id in source
    assert "\\n  schedule:" not in source
    assert "\\n  push:" not in source
    assert "VELTRIX_SESSION_ID:" in source
    assert "XAUUSD-only" in source
    assert "AllowLiveTrading=0" in source
    assert "AllowDllImport=0" in source
    assert "veltrix-exness-demo-ticks-${{ github.run_number }}" in source


def test_phase8_collector_binds_session_id_into_manifest_and_rejects_unknown_ids():
    source = (ROOT / "tools/mt5_demo_tick_collector.py").read_text(encoding="utf-8")
    assert 'session_id = os.environ.get("VELTRIX_SESSION_ID", "")' in source
    assert '"session_id": session_id' in source


def test_phase8_intake_requires_manifest_bound_validation_session_id():
    source = (ROOT / "tools/prepare_xauusd_walk_forward_catalog.py").read_text(encoding="utf-8")
    assert 'manifest.get("session_id") != sid' in source
    assert "manifest session_id does not match" in source
    assert "distinct dates required" in source
    assert "requires all preregistered eligible sessions together" in source


def test_phase8_collection_workflow_has_no_trade_execution_or_scheduled_trigger():
    source = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8").lower()
    assert "schedule:" not in source
    assert "ordersend(" not in source
    assert "ordersendasync(" not in source
    assert "allowlivetrading=0" in source
    assert "allowdllimport=0" in source
