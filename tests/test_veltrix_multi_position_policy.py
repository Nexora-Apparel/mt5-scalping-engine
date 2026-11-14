from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOCATOR = ROOT / "MQL5/Include/Veltrix/RiskAllocator.mqh"
CONTROLS = ROOT / "MQL5/Include/Veltrix/RiskControls.mqh"
REGISTRY = ROOT / "MQL5/Include/Veltrix/PositionRegistry.mqh"
GUARD = ROOT / "MQL5/Include/Veltrix/ExecutionGuard.mqh"
POLICY = ROOT / "docs/XAUUSD_MULTI_POSITION_SCALPING_V1.md"


def test_risk_allocator_has_no_simultaneous_position_count_ceiling():
    source = ALLOCATOR.read_text(encoding="utf-8")
    assert "int    open_positions;" in source
    assert "int    max_positions;" not in source
    assert "request.open_positions>=request.max_positions" not in source
    assert "Position count is intentionally uncapped" in source
    assert "current_open_risk_money" in source
    assert "max_portfolio_risk_percent" in source
    assert "MathFloor" in source


def test_risk_controls_no_longer_require_exactly_one_position():
    source = CONTROLS.read_text(encoding="utf-8")
    assert "max_positions" not in source
    assert "config.max_positions!=1" not in source
    assert "no simultaneous-position count limit" in source


def test_position_registry_tracks_independent_scalp_lifecycles():
    source = REGISTRY.read_text(encoding="utf-8")
    assert "RegisterConfirmedOpen" in source
    assert "m_records[]" in source
    assert "hold_seconds<10 || hold_seconds>60" in source
    assert "EvaluateCloseDeadlines" in source
    assert "ConfirmClosed" in source


def test_broker_margin_and_hedging_constraints_remain_mandatory():
    source = GUARD.read_text(encoding="utf-8")
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in source
    assert "OrderCalcMargin" in source
    assert "ACCOUNT_MARGIN_FREE" in source
    assert "margin_reserve_money" in source
    assert "intent.take_profit<=0.0" in source
    assert "Take-profit is mandatory" in source
    assert "target_distance+point*1e-6" in source
    assert "SYMBOL_VOLUME_MIN" in source or "SYMBOL_VOLUME_MIN" in (ROOT / "MQL5/Include/Veltrix/MarketGuard.mqh").read_text(encoding="utf-8")


def test_multi_position_policy_preserves_phase8_and_daily_loss_safety_boundary():
    source = POLICY.read_text(encoding="utf-8")
    assert "Phase 8" in source
    assert "one open position per candidate configuration" in source
    assert "0.50% of equity" in source
    assert "15.00% of verified server-day starting equity" in source
    assert "50.00% of the owner-verified original deposit" in source
    assert "no daily profit target or profit cap" in source.lower()
    assert "Floating PnL" in source
    assert "No daily minimum trade count" in source
    assert "No fixed simultaneous-position count ceiling" in source


def test_future_execution_apis_remain_absent_from_risk_components():
    paths = (
        ALLOCATOR,
        CONTROLS,
        REGISTRY,
        GUARD,
    )
    forbidden = ("ordersend(", "ordersendasync(", "positionopen(",
                 "positionclose(", "positionmodify(", "ctrade")
    for path in paths:
        lowered = path.read_text(encoding="utf-8").lower()
        assert not [token for token in forbidden if token in lowered], path



def test_risk_controls_sizes_against_the_portfolio_exposure_ledger():
    source = CONTROLS.read_text(encoding="utf-8")
    assert '#include "PortfolioExposureLedger.mqh"' in source
    assert "const CVxPortfolioExposureLedger &exposures" in source
    assert "exposures.AggregateOpenRiskMoney()" in source
    assert "exposures.ActiveCount()" in source



def test_closed_position_registry_has_explicit_memory_compaction():
    registry = (ROOT / "MQL5/Include/Veltrix/PositionRegistry.mqh").read_text(encoding="utf-8")
    ledger = (ROOT / "MQL5/Include/Veltrix/PortfolioExposureLedger.mqh").read_text(encoding="utf-8")
    assert "int PruneClosed(void)" in registry
    assert "return (PruneClosed()>0);" in registry
    assert "broker_close_deal_confirmed" in registry
    assert "ArrayResize(m_records,size-1)" in registry
    assert "ArrayResize(m_items,size-1)" in ledger



def test_multi_position_policy_keeps_analysis_running_without_cooldown_or_loss_streak_pause():
    import json
    policy = json.loads((ROOT / "research/xauusd_multi_position_policy_v1.json").read_text(encoding="utf-8"))
    controls = CONTROLS.read_text(encoding="utf-8")
    assert policy["risk_controls"]["cooldown_seconds"] == 0
    assert policy["risk_controls"]["max_consecutive_losses"] == 0
    assert "config.cooldown_seconds<0" in controls
    assert "m_config.cooldown_seconds>0" in controls
    assert "m_config.max_consecutive_losses>0" in controls



def test_manual_daily_loss_reactivation_requirement_is_explicit_and_not_misrepresented():
    import json
    policy = json.loads((ROOT / "research/xauusd_multi_position_policy_v1.json").read_text(encoding="utf-8"))
    controls = CONTROLS.read_text(encoding="utf-8")
    assert policy["risk_controls"]["daily_loss_reactivation"] == "MANUAL_OWNER_CONFIRMATION_REQUIRED"
    assert policy["risk_controls"]["current_implementation_reactivation"] == "DAILY_REARM_JOURNAL_PENDING_LATEST_RUNTIME_VALIDATION; OVERALL_LOSS_GUARD_INTEGRATED_IN_CVX_RISK_CONTROLS_PENDING_LATEST_COMPILE_RUNTIME_AND_TRUSTED_OWNER_INTERFACE"
    day_reset = controls.split("bool BeginServerDay", 1)[1].split("bool EvaluateDailyLoss", 1)[0]
    assert "m_daily_loss_locked=false" not in day_reset
    assert "owner-rearmed" in day_reset
    assert "owner-controlled manual reactivation" in (ROOT / "docs/XAUUSD_MULTI_POSITION_SCALPING_V1.md").read_text(encoding="utf-8")
    assert "RearmDailyLossLock" in controls
    assert "DAILY_REARM" in (ROOT / "MQL5/Include/Veltrix/RiskJournal.mqh").read_text(encoding="utf-8")



def test_mql5_runtime_harness_initializes_with_unlimited_trade_frequency_policy():
    source = (ROOT / "MQL5/Scripts/RiskControlsRuntimeTest.mq5").read_text(encoding="utf-8")
    assert "config.cooldown_seconds=0" in source
    assert "config.max_consecutive_losses=0" in source


def test_overall_loss_guard_is_mandatory_in_risk_intent_approval_path():
    controls = CONTROLS.read_text(encoding="utf-8")
    guard = (ROOT / "MQL5/Include/Veltrix/OverallAccountLossGuard.mqh").read_text(encoding="utf-8")
    assert '#include "OverallAccountLossGuard.mqh"' in controls
    assert "original_deposit_verified" in controls
    assert "m_overall_guard.Init" in controls
    assert "m_overall_guard.Evaluate" in controls
    assert "RearmOverallAccountLossLock" in controls
    assert "m_overall_guard.IsLocked()" in controls
    assert "ACCOUNT_EQUITY" in guard
    assert "m_original_deposit" in guard
    assert "m_loss_limit_percent=50.0" in guard


def test_risk_control_runtime_and_process_restart_fixtures_pin_verified_deposit():
    runtime = (ROOT / "MQL5/Scripts/RiskControlsRuntimeTest.mq5").read_text(encoding="utf-8")
    seed = (ROOT / "MQL5/Scripts/RiskControlsRestartSeed.mq5").read_text(encoding="utf-8")
    verify = (ROOT / "MQL5/Scripts/RiskControlsRestartVerify.mq5").read_text(encoding="utf-8")
    for source in (runtime, seed, verify):
        assert "verified_original_deposit=10000.0" in source
        assert "original_deposit_verified=true" in source
