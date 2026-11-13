from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase8_collection_is_bounded_to_four_scheduled_dates_and_not_push_triggered():
    source = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8")
    assert 'cron: "30 10 14-17 11 *"' in source
    assert "workflow_dispatch:" in source
    assert "\n  push:" not in source
    assert "XAUUSD-only" in source
    assert "AllowLiveTrading=0" in source
    assert "AllowDllImport=0" in source
    assert "veltrix-exness-demo-ticks-${{ github.run_number }}" in source


def test_phase8_validation_refresh_maps_only_successful_scheduled_runs_on_preregistered_dates():
    source = (ROOT / ".github/workflows/phase8-validation-refresh.yml").read_text(encoding="utf-8")
    for date, session_id in (
        ("2026-11-14", "validation_01"),
        ("2026-11-15", "validation_02"),
        ("2026-11-16", "validation_03"),
        ("2026-11-17", "validation_04"),
    ):
        assert date in source
        assert session_id in source
    assert 'event") != "schedule"' in source
    assert 'status") != "completed"' in source
    assert 'conclusion") != "success"' in source
    assert "prepare_xauusd_walk_forward_catalog" in source
    assert "mt5_xauusd_walk_forward" in source
    assert "final_holdout" not in source.lower()
    assert "actions: read" in source
    assert "contents: read" in source


def test_phase8_collection_orchestrator_has_no_trade_execution_or_secret_access():
    source = (ROOT / ".github/workflows/phase8-validation-refresh.yml").read_text(encoding="utf-8").lower()
    for forbidden in ("mt5_password", "mt5_login", "ordersend(", "ordersendasync(", "ctrade", "trade_action_deal"):
        assert forbidden not in source
