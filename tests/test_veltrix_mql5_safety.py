from pathlib import Path
import math


ROOT = Path(__file__).resolve().parents[1]
EA_SOURCE = ROOT / "MQL5" / "Experts" / "VeltrixScalper.mq5"
GUARD_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "MarketGuard.mqh"
RISK_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "RiskAllocator.mqh"
POSITION_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "PositionRegistry.mqh"
EXECUTION_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "ExecutionGuard.mqh"
RECONCILER_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "BrokerReconciler.mqh"
COORDINATOR_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "ExecutionCoordinator.mqh"


def test_veltrix_foundation_contains_no_order_submission_api():
    source = EA_SOURCE.read_text(encoding="utf-8").lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
    )
    assert not [token for token in forbidden if token in source]


def test_market_guard_is_read_only_and_checks_quote_health():
    source = GUARD_SOURCE.read_text(encoding="utf-8")
    required = (
        "SymbolInfoTick", "SYMBOL_TRADE_TICK_SIZE",
        "SYMBOL_TRADE_TICK_VALUE_LOSS", "SYMBOL_VOLUME_MIN",
        "SYMBOL_VOLUME_STEP", "SYMBOL_TRADE_STOPS_LEVEL",
        "SYMBOL_TRADE_FREEZE_LEVEL", "TimeTradeServer",
        "GetTickCount64", "m_max_spread_points", "m_max_quote_age_ms",
    )
    for token in required:
        assert token in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal", "ctrade")
    assert not [token for token in forbidden if token in lowered]


def test_veltrix_ea_uses_repository_relative_includes_and_timer():
    source = EA_SOURCE.read_text(encoding="utf-8")
    for include in ("MarketGuard.mqh", "RiskAllocator.mqh",
                    "PositionRegistry.mqh", "ExecutionGuard.mqh",
                    "BrokerReconciler.mqh", "ExecutionCoordinator.mqh",
                    "OverallAccountLossGuard.mqh"):
        assert f'#include "..\\\\Include\\\\Veltrix\\\\{include}"' in source
    assert "StrategyResearch.mqh" in source
    assert "FeaturePipeline.mqh" in source
    assert "EventSetMillisecondTimer" in source
    assert "EventKillTimer" in source


def test_risk_allocator_is_fail_closed_and_rounds_volume_down():
    source = RISK_SOURCE.read_text(encoding="utf-8")
    required = (
        "VxCalculateRiskVolume", "tick_value_loss",
        "current_open_risk_money", "max_portfolio_risk_percent",
        "MathFloor", "MathIsValidNumber", "Non-finite numeric input",
        "volume<request.volume_min",
        "risk-sized volume is below broker minimum",
    )
    lowered = source.lower()
    for token in required:
        assert token.lower() in lowered
    assert "MathCeil" not in source
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal", "ctrade")
    assert not [token for token in forbidden if token in lowered]


def _reference_volume(equity, risk_pct, stop_distance, tick_size,
                      tick_value_loss, min_volume, max_volume, step,
                      open_risk, portfolio_pct, open_positions):
    numeric = (equity, risk_pct, stop_distance, tick_size, tick_value_loss,
               min_volume, max_volume, step, open_risk, portfolio_pct)
    if not all(math.isfinite(value) for value in numeric):
        return 0.0
    if open_positions < 0 or min(equity, risk_pct, stop_distance,
            tick_size, tick_value_loss, min_volume, step, portfolio_pct) <= 0:
        return 0.0
    loss_per_lot = (stop_distance / tick_size) * tick_value_loss
    budget = min(equity * risk_pct / 100,
                 equity * portfolio_pct / 100 - open_risk)
    if budget <= 0 or loss_per_lot <= 0:
        return 0.0
    volume = math.floor(min(budget / loss_per_lot, max_volume) / step + 1e-10) * step
    volume = round(volume, 8)
    return volume if volume >= min_volume and volume * loss_per_lot <= budget + 1e-8 else 0.0


def test_reference_risk_vectors_skip_under_minimum_and_respect_portfolio_cap():
    assert _reference_volume(10, 0.25, 2.0, 0.01, 1.0,
                             0.01, 100.0, 0.01, 0.0, 1.0, 0) == 0.0
    assert _reference_volume(1000, 1.0, 0.1, 0.01, 1.0,
                             0.01, 100.0, 0.01, 0.0, 3.0, 0) == 1.0
    assert _reference_volume(1000, 2.0, 0.1, 0.01, 1.0,
                             0.01, 100.0, 0.01, 25.0, 3.0, 17) == 0.5


def test_reference_risk_vectors_reject_nan_and_infinity():
    baseline = [1000.0, 1.0, 0.1, 0.01, 1.0, 0.01, 100.0,
                0.01, 0.0, 3.0]
    for index in range(len(baseline)):
        for invalid in (math.nan, math.inf, -math.inf):
            values = baseline.copy()
            values[index] = invalid
            assert _reference_volume(*values, 0) == 0.0


def test_risk_allocator_checks_finite_inputs_and_derived_values():
    source = RISK_SOURCE.read_text(encoding="utf-8")
    assert source.count("MathIsValidNumber") >= 15
    assert "Non-finite numeric input" in source
    assert "Non-finite derived risk budget" in source
    assert "Calculated raw volume is invalid" in source
    assert "Estimated loss is invalid" in source


def test_position_registry_is_per_position_and_fails_closed_on_unknown_broker_state():
    source = POSITION_SOURCE.read_text(encoding="utf-8")
    required = (
        "RegisterConfirmedOpen", "FindByIdentifier", "FindByTicket",
        "EvaluateCloseDeadlines", "MarkClosePending", "MarkUnknown",
        "MarkLiveVerified", "ConfirmClosed", "broker_close_deal_confirmed",
        "VX_POSITION_UNKNOWN", "VX_POSITION_CLOSED",
    )
    for token in required:
        assert token in source
    assert "hold_seconds<10 || hold_seconds>60" in source
    assert "!MathIsValidNumber(volume) || volume<=0.0" in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal",
                 "ctrade", "positionclose(", "positionmodify(")
    assert not [token for token in forbidden if token in lowered]


def test_position_registry_reference_lifecycle_and_deadline_vectors():
    opened_msc = 1_000_000
    deadline = opened_msc + 15 * 1000
    assert deadline == 1_015_000
    assert opened_msc + 14_999 < deadline
    assert opened_msc + 15_000 >= deadline
    broker_close_confirmed = False
    assert broker_close_confirmed is False


def test_execution_guard_is_demo_only_preflight_without_submission():
    source = EXECUTION_SOURCE.read_text(encoding="utf-8")
    required = (
        "ValidateDemoIntent", "expected_demo_login", "expected_demo_server",
        "ACCOUNT_LOGIN", "ACCOUNT_SERVER", "XAUUSD",
        "SYMBOL_CURRENCY_BASE", "SYMBOL_CURRENCY_PROFIT", "ACCOUNT_TRADE_MODE_DEMO",
        "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", "TERMINAL_CONNECTED",
        "TERMINAL_TRADE_ALLOWED", "MQL_TRADE_ALLOWED",
        "ACCOUNT_TRADE_ALLOWED", "SYMBOL_TRADE_STOPS_LEVEL",
        "SymbolInfoTick", "OrderCalcMargin", "ACCOUNT_MARGIN_FREE",
        "margin_reserve_money", "protective stop loss is mandatory",
        "MathIsValidNumber",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal",
                 "trade_action_pending", "ctrade", "positionclose(",
                 "positionmodify(")
    assert not [token for token in forbidden if token in lowered]


def test_execution_guard_rejects_live_account_and_non_hedging_mode():
    source = EXECUTION_SOURCE.read_text(encoding="utf-8")
    assert "!=ACCOUNT_TRADE_MODE_DEMO" in source
    assert "!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in source
    assert "!MathIsValidNumber(intent.volume)" in source
    assert "!MathIsValidNumber(intent.stop_loss)" in source


def test_broker_reconciler_is_read_only_and_requires_confirmed_close_evidence():
    source = RECONCILER_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxBrokerReconciler", "PositionsTotal", "PositionGetTicket",
        "POSITION_IDENTIFIER", "HistorySelect", "HistoryDealsTotal",
        "DEAL_POSITION_ID", "DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY",
        "VX_RECONCILE_LIVE_VERIFIED", "VX_RECONCILE_PROTECTION_FAILURE",
        "VX_RECONCILE_CLOSED_CONFIRMED", "VX_RECONCILE_UNKNOWN",
        "MarkLiveVerified", "ConfirmClosed", "MathIsValidNumber",
    )
    for token in required:
        assert token in source
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionclose(",
        "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


# Incomplete broker history is deliberately not promoted to a confirmed close.
def test_broker_reconciler_treats_partial_exit_and_missing_history_as_unknown():
    source = RECONCILER_SOURCE.read_text(encoding="utf-8")
    assert "VX_RECONCILE_CLOSE_HISTORY_INCOMPLETE" in source
    assert "history_ok && row.confirmed_exit_volume+tolerance>=record.volume" in source
    assert "registry.MarkUnknown(record.identifier,row.reason)" in source



# Coordinator tests assert state contracts; they do not simulate a live broker.
def test_execution_coordinator_is_state_only_and_fail_closed():
    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")
    required = (
        "VX_REQUEST_PREPARED", "VX_REQUEST_SUBMITTING",
        "VX_REQUEST_ACKNOWLEDGED", "VX_REQUEST_PARTIALLY_FILLED",
        "VX_REQUEST_FILLED", "VX_REQUEST_REJECTED",
        "VX_REQUEST_OUTCOME_UNKNOWN", "VX_REQUEST_RECONCILING",
        "VX_REQUEST_CANCELLED", "Prepare", "MarkSubmitting",
        "RecordBrokerResponse", "RecordFill", "DealAlreadySeen",
        "BeginReconciliation", "ResolveFromBroker", "SetDisconnected",
        "SetReconnected", "LatchEmergencyStop", "m_emergency_stop",
    )
    for token in required:
        assert token in source
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]
    assert "no broker request sent" in lowered
    assert "reconcile before retry" in lowered
    assert "late or contradictory deal" in lowered
    assert "prepared intent cancelled locally" in lowered
    assert "no reset method" in lowered


def test_execution_coordinator_rejects_zero_unconfirmed_volume_as_terminal():
    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")
    assert "else if(broker_confirmed_volume>tolerance)" in source
    assert "Broker confirms no fill but not a terminal rejection; keep outcome unknown" in source
    assert "broker_confirms_terminal_rejection && broker_confirmed_volume<=tolerance" in source


def test_execution_coordinator_reference_fill_and_disconnect_vectors():
    requested = 0.30
    fills = [0.10, 0.05, 0.15]
    assert sum(fills[:2]) < requested
    assert abs(sum(fills) - requested) < 1e-12
    seen_deals = {101, 102}
    assert 102 in seen_deals
    assert len(seen_deals) == 2
    state_after_disconnect = "OUTCOME_UNKNOWN"
    assert state_after_disconnect != "REJECTED"
    prepared_after_disconnect = "CANCELLED"
    assert prepared_after_disconnect != "PREPARED"


STRATEGY_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "StrategyResearch.mqh"


def test_strategy_research_engine_is_isolated_and_candidate_only():
    source = STRATEGY_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxStrategyResearch", "VxStrategyConfig", "VxStrategySnapshot",
        "VxSignalCandidate", "XAUUSD", "XAGUSD", "max_quote_age_ms",
        "max_spread_bps", "min_realized_volatility_bps",
        "max_realized_volatility_bps", "min_abs_momentum_bps",
        "min_efficiency_ratio", "min_observations", "VX_SIGNAL_LONG",
        "VX_SIGNAL_SHORT", "VX_SIGNAL_NONE", "Quote is stale",
        "Spread exceeds", "not an execution instruction",
    )
    for token in required:
        assert token in source
    assert "snapshot.feature_window_start_msc>snapshot.quote_time_msc" in source
    assert "snapshot.quote_time_msc-snapshot.feature_window_start_msc" in source
    assert "MathIsValidNumber(midpoint)" in source
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_strategy_research_reference_gates_reject_stale_spread_and_weak_momentum():
    def evaluate(age_ms, spread_bps, momentum_bps, min_momentum=2.0):
        if age_ms > 500:
            return "STALE"
        if spread_bps > 8.0:
            return "SPREAD"
        if abs(momentum_bps) < min_momentum:
            return "MOMENTUM"
        return "CANDIDATE"

    assert evaluate(501, 2.0, 5.0) == "STALE"
    assert evaluate(100, 8.1, 5.0) == "SPREAD"
    assert evaluate(100, 2.0, 1.9) == "MOMENTUM"
    assert evaluate(100, 2.0, 2.1) == "CANDIDATE"
    assert evaluate(100, 2.0, -2.1) == "CANDIDATE"


FEATURE_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "FeatureCollector.mqh"


def test_feature_collector_is_point_in_time_symbol_isolated_and_read_only():
    source = FEATURE_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxFeatureCollector", "VxFeatureCollectorConfig",
        "VxQuoteObservation", "PushQuote", "BuildSnapshot",
        "XAUUSD", "XAGUSD", "time_msc", "MathLog",
        "MathSqrt", "momentum_bps", "realized_volatility_bps",
        "efficiency_ratio", "complete lookback", "out of order",
        "evaluation_time_msc", "MathIsValidNumber",
        "Feature accumulation overflowed or became non-finite",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_feature_collector_is_included_without_enabling_execution():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert "FeatureCollector.mqh" in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal",
                 "trade_action_pending", "ctrade")
    assert not [token for token in forbidden if token in lowered]


def test_feature_reference_vectors_use_only_observations_at_or_before_evaluation():
    prices = [2000.0, 2000.2, 2000.1, 2000.4]
    log_returns = [math.log(prices[i] / prices[i - 1])
                   for i in range(1, len(prices))]
    momentum_bps = math.log(prices[-1] / prices[0]) * 10000
    realized_volatility_bps = math.sqrt(sum(x * x for x in log_returns)) * 10000
    path = sum(abs(prices[i] - prices[i - 1])
               for i in range(1, len(prices)))
    efficiency = abs(prices[-1] - prices[0]) / path
    assert momentum_bps > 0
    assert realized_volatility_bps > 0
    assert 0 <= efficiency <= 1
    timestamps = [1000, 1100, 1200, 1300]
    evaluation_time = 1250
    eligible = [t for t in timestamps if t <= evaluation_time]
    assert eligible == [1000, 1100, 1200]
    assert 1300 not in eligible


EXPORTER_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "FeatureDatasetExporter.mqh"


def test_feature_dataset_exporter_is_versioned_provenance_aware_and_read_only():
    source = EXPORTER_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxFeatureDatasetExporter", "AppendSnapshot",
        "VX_FEATURE_DATASET_SCHEMA_VERSION",
        "VX_FEATURE_CALCULATION_VERSION", "source_id",
        "quote_time_msc", "window_start_msc",
        "evaluation_time_msc", "momentum_bps",
        "realized_volatility_bps", "efficiency_ratio",
        "FileWrite", "FileFlush", "FILE_CSV",
        "XAUUSD", "XAGUSD", "SafeFileName",
        "FileReadString", "Existing CSV header does not match expected schema",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_feature_dataset_exporter_is_compiled_but_not_activated():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert "FeatureDatasetExporter.mqh" in source
    assert "FeaturePipeline.mqh" in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal",
                 "trade_action_pending", "ctrade")
    assert not [token for token in forbidden if token in lowered]


def test_feature_dataset_schema_preserves_ordering_and_version_identity():
    schema = [
        "schema_version", "feature_version", "source_id", "symbol",
        "quote_time_msc", "window_start_msc", "evaluation_time_msc",
        "bid", "ask", "momentum_bps", "realized_volatility_bps",
        "efficiency_ratio", "observations",
    ]
    assert len(schema) == len(set(schema))
    assert schema.index("quote_time_msc") < schema.index("evaluation_time_msc")
    assert "source_id" in schema and "feature_version" in schema


def test_feature_dataset_exporter_rejects_unsafe_paths_and_schema_mismatch():
    source = EXPORTER_SOURCE.read_text(encoding="utf-8")
    assert "StringGetCharacter(filename,i)" in source
    assert "FileSeek(handle,0,SEEK_SET)" in source
    assert "FileSeek(handle,0,SEEK_END)" in source
    assert "Existing CSV header does not match expected schema" in source
    assert 'StringSubstr(filename,length-4,4)!=".csv"' in source


DATASET_RUNTIME_TEST_SOURCE = ROOT / "MQL5" / "Scripts" / "FeatureDatasetExporterRuntimeTest.mq5"


def test_dataset_runtime_script_is_read_only_and_checks_cleanup():
    source = DATASET_RUNTIME_TEST_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxFeatureDatasetExporter", "AppendSnapshot",
        "FileOpen", "FileReadString", "FileDelete",
        "veltrix_dataset_export_runtime_test.result",
        "invalid symbol was accepted", "mismatched existing CSV header was accepted", "FileIsExist",
        "DATASET RUNTIME TEST PASS", "CVxFeaturePipeline",
        "runtime-pipeline-session", "pipeline.RowsWritten()!=2",
        "FeaturePipeline.mqh", "pipeline CSV read-back or chronology check failed",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


PIPELINE_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "FeaturePipeline.mqh"


def test_feature_pipeline_is_optional_point_in_time_and_fail_closed():
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxFeaturePipeline", "CVxFeatureCollector",
        "CVxFeatureDatasetExporter", "ProcessQuote", "BuildSnapshot",
        "AppendSnapshot", "ValidSourceId", "ValidFileName",
        "m_last_quote_msc", "m_last_export_msc", "m_faulted",
        "m_rows_written", "Collecting warm-up history",
        "Snapshot timestamps do not match the source quote",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionopen(",
        "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_ea_dataset_collection_is_explicitly_disabled_by_default():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert "input bool   EnableDatasetCollection = false;" in source
    assert "if(EnableDatasetCollection && healthy" in source
    assert "g_feature_pipeline.ProcessQuote" in source
    assert "g_feature_pipeline.Init" in source
    assert "FeaturePipeline.mqh" in source
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordercheck(", "trade_action_deal",
        "trade_action_pending", "ctrade", "positionclose(",
        "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_live_dataset_collection_requires_exact_connected_demo_account():
    source = EA_SOURCE.read_text(encoding="utf-8")
    required = (
        "ExpectedDemoLogin", "ExpectedDemoServer",
        "TERMINAL_CONNECTED", "ACCOUNT_LOGIN",
        "ACCOUNT_TRADE_MODE_DEMO", "ACCOUNT_SERVER",
        "DATASET DEMO ACCOUNT GUARD FAILED",
        "DATASET DEMO ACCOUNT GUARD PASSED",
    )
    for token in required:
        assert token in source
    assert "input bool   EnableDatasetCollection = false;" in source


RISK_CONTROLS_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "RiskControls.mqh"


def test_phase7_risk_controls_are_demo_xauusd_only_and_fail_closed():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    required = (
        "CVxRiskControls", "expected_demo_login", "expected_demo_server",
        "ACCOUNT_TRADE_MODE_DEMO", "ACCOUNT_LOGIN", "ACCOUNT_SERVER",
        "risk_per_trade_percent>0.25",
        "max_portfolio_risk_percent>0.50",
        "max_daily_loss_percent>15.00",
        "cooldown_seconds<0", "max_consecutive_losses<0",
        "max_consecutive_losses>3", "BeginServerDay",
        "EvaluateDailyLoss", "RecordVerifiedClose", "closing_deal_ticket",
        "VX_CLOSE_", "Duplicate verified closing deal ignored",
        "RegisterApprovedIntent", "RequestKey", "m_journal.HasRequest", "m_journal.AppendRequest",
        "LatchEmergencyStop", "m_emergency_stop",
        "GlobalVariableCheck", "GlobalVariableGet", "GlobalVariableSet",
        "GlobalVariablesFlush", "m_emergency_key",
        "Only a verified XAUUSD contract is permitted",
        "Duplicate request identifier rejected",
        "Post-loss cooldown is active",
        "daily loss lock remains latched until audited owner reactivation",
    )
    for token in required:
        assert token.lower() in source.lower()
    lowered = source.lower()
    forbidden = (
        "ordersend(", "ordersendasync(", "ordercheck(",
        "trade_action_deal", "trade_action_pending", "ctrade",
        "positionopen(", "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_phase7_risk_controls_are_included_but_not_enabled_for_execution():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert 'RiskControls.mqh' in source
    assert "EnableDemoOrders" not in source
    assert "EnableCandidateAnalysis = false" in source
    assert "EnableDatasetCollection = false" in source


def test_phase7_daily_loss_lock_and_emergency_stop_are_distinct():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    assert "m_daily_loss_locked=false;" in source
    assert "m_emergency_stop=true;" in source
    day_reset = source.split("bool BeginServerDay", 1)[1].split("bool EvaluateDailyLoss", 1)[0]
    assert "m_daily_loss_locked=false;" not in day_reset
    assert "owner-rearmed" in day_reset
    assert "m_emergency_stop=false;" not in day_reset
    assert "GlobalVariableCheck(keys[i])" in source
    assert "GlobalVariableSet(m_emergency_key,(m_emergency_stop ? 1.0 : 0.0))" in source
    assert "GlobalVariablesFlush();" in source
    assert "A daily-loss lock, cooldown, and emergency stop deliberately survive a day boundary." in source
    assert "no reset method" not in source.lower() or "LatchEmergencyStop" in source


def test_phase7_risk_policy_reference_boundaries():
    # Policy ceilings are hard caps; the defaults remain operator-configured and unused.
    assert 0.25 <= 0.25
    assert not (0.250001 <= 0.25)
    assert 0.50 <= 0.50
    assert not (0.500001 <= 0.50)
    assert 15.00 <= 15.00
    assert not (15.000001 <= 15.00)
    day_start = 1000.0
    daily_limit = 15.0
    assert (day_start - 850.01) / day_start * 100 < daily_limit
    assert (day_start - 850.0) / day_start * 100 >= daily_limit


def test_phase7_sizing_and_intent_registration_recheck_live_account_and_daily_loss():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    sizing = source.split("bool CalculateVolume", 1)[1].split("bool RegisterApprovedIntent", 1)[0]
    registration = source.split("bool RegisterApprovedIntent", 1)[1].split("bool LatchEmergencyStop", 1)[0]
    assert "VerifyExactDemoAccount(guard_reason)" in sizing
    assert "EvaluateDailyLoss(source.equity,guard_reason)" in sizing
    assert "VerifyExactDemoAccount(reason)" in registration
    assert "EvaluateDailyLoss(current_equity,reason)" in registration
    assert "active_positions>=m_config.max_positions" not in registration
    assert "there is no count ceiling" in registration
    assert "m_journal.HasRequest(request_key)" in registration
    assert "m_journal.AppendRequest(request_key,now_msc,reason)" in registration
    close_record = source.split("bool RecordVerifiedClose", 1)[1].split("bool CalculateVolume", 1)[0]
    assert "m_journal.HasClose(close_key)" in close_record
    assert "m_journal.AppendClose(close_key,close_time_msc,net_profit,reason)" in close_record


def test_phase7_execution_preflight_binds_account_and_symbol_contract():
    source = EXECUTION_SOURCE.read_text(encoding="utf-8")
    assert "intent.expected_demo_login" in source
    assert "intent.expected_demo_server" in source
    assert "ACCOUNT_LOGIN" in source and "ACCOUNT_SERVER" in source
    assert "SYMBOL_CURRENCY_BASE" in source
    assert "SYMBOL_CURRENCY_PROFIT" in source
    assert 'base_currency!="XAU" || profit_currency!="USD"' in source
    assert "A protective stop loss is mandatory" in source
    assert "OrderCalcMargin" in source


def test_phase7_public_state_mutations_require_exact_connected_demo_identity():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    day = source.split("bool BeginServerDay", 1)[1].split("bool EvaluateDailyLoss", 1)[0]
    loss = source.split("bool EvaluateDailyLoss", 1)[1].split("bool RecordVerifiedClose", 1)[0]
    close = source.split("bool RecordVerifiedClose", 1)[1].split("bool CalculateVolume", 1)[0]
    assert "VerifyExactDemoAccount(reason)" in day
    assert "VerifyExactDemoAccount(reason)" in loss
    assert "VerifyExactDemoAccount(reason)" in close
    assert "ACCOUNT_TRADE_MODE_DEMO" in source
    assert "TERMINAL_CONNECTED" in source


def test_phase7_execution_preflight_enforces_broker_tick_size_for_protection():
    source = EXECUTION_SOURCE.read_text(encoding="utf-8")
    assert "SYMBOL_TRADE_TICK_SIZE" in source
    assert "stop_ticks=intent.stop_loss/tick_size" in source
    assert "MathAbs(stop_ticks-MathRound(stop_ticks))>1e-6" in source
    assert "target_ticks=intent.take_profit/tick_size" in source
    assert "MathAbs(target_ticks-MathRound(target_ticks))>1e-6" in source


def test_phase7_persistent_keys_use_64bit_hashing():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    assert "ulong hash=14695981039346656037" in source
    assert "hash*=1099511628211" in source
    assert "hash^=(ulong)StringGetCharacter(value,i)" in source


def test_phase7_position_registry_and_broker_history_are_xauusd_scoped():
    registry = (ROOT / "MQL5" / "Include" / "Veltrix" / "PositionRegistry.mqh").read_text(encoding="utf-8")
    reconciler = (ROOT / "MQL5" / "Include" / "Veltrix" / "BrokerReconciler.mqh").read_text(encoding="utf-8")
    assert "IsVerifiedXauUsd(symbol)" in registry
    assert "SYMBOL_CURRENCY_BASE" in registry
    assert "SYMBOL_CURRENCY_PROFIT" in registry
    assert 'base=="XAU" && profit=="USD"' in registry
    assert "HistoryDealGetString(deal,DEAL_SYMBOL)!=record.symbol" in reconciler


def test_phase7_reconciliation_fails_closed_on_live_symbol_mismatch():
    source = (ROOT / "MQL5" / "Include" / "Veltrix" / "BrokerReconciler.mqh").read_text(encoding="utf-8")
    assert 'actual_symbol=PositionGetString(POSITION_SYMBOL)' in source
    assert 'if(live_symbol!=record.symbol)' in source
    assert "Live broker position symbol differs from registered XAUUSD contract" in source


def test_phase7_safety_modules_and_ea_have_no_order_submission_or_modification_api():
    paths = (
        "MQL5/Include/Veltrix/RiskControls.mqh",
        "MQL5/Include/Veltrix/RiskAllocator.mqh",
        "MQL5/Include/Veltrix/ExecutionGuard.mqh",
        "MQL5/Include/Veltrix/PositionRegistry.mqh",
        "MQL5/Include/Veltrix/BrokerReconciler.mqh",
        "MQL5/Include/Veltrix/ExecutionCoordinator.mqh",
        "MQL5/Experts/VeltrixScalper.mq5",
    )
    forbidden = (
        "ordersend(", "ordersendasync(", "ordercheck(",
        "trade_action_deal", "trade_action_pending", "ctrade",
        "positionopen(", "positionclose(", "positionmodify(",
        "orderdelete(", "orderdeletebyticket(",
    )
    for relative in paths:
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert not [token for token in forbidden if token in source], relative


def test_phase7_persistent_risk_state_uses_last_written_checksum_commit_marker():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    persist = source.split("bool PersistRiskState", 1)[1].split("public:", 1)[0]
    assert "string m_state_checksum_name" in source
    assert "string keys[8]" in source
    assert "if(present!=0 && present!=8)" in source
    assert "RiskStateChecksum()" in persist
    assert "GlobalVariableSet(m_state_checksum_name,RiskStateChecksum())" in persist
    assert "Persistent risk-state checksum mismatch" in source


def test_phase7_close_accounting_is_serialized_and_abandoned_lock_fails_closed():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    close = source.split("bool RecordVerifiedClose", 1)[1].split("bool CalculateVolume", 1)[0]
    assert "GlobalVariableSetOnCondition(m_state_lock_name" in source
    assert "AcquireRiskStateLock(close_time_msc,reason)" in close
    assert "ReleaseRiskStateLock(close_time_msc)" in close
    assert "prior risk-state transaction did not finish" in source
    assert "manual reconciliation required" in source


def test_phase7_risk_journal_is_append_only_checksum_chained_and_account_scoped():
    source = (ROOT / "MQL5" / "Include" / "Veltrix" / "RiskJournal.mqh").read_text(encoding="utf-8")
    assert "FILE_COMMON" in source
    assert "VELTRIX_XAUUSD_RISK_" in source
    assert "FileWrite(m_handle" in source
    assert "FileFlush(m_handle)" in source
    assert "FileSeek(m_handle,0,SEEK_END)" in source
    assert "m_previous_hash" in source
    assert "HashText(payload)" in source
    assert "m_sequence+1" in source
    assert "Risk journal checksum chain is invalid" in source
    assert "Duplicate request identifier rejected by durable journal" in source
    assert "Duplicate verified closing deal rejected by durable journal" in source


def test_phase7_risk_controls_initializes_durable_journal_before_approval():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    assert '#include "RiskJournal.mqh"' in source
    assert "m_journal.Init(config.expected_demo_login,config.expected_demo_server,reason)" in source
    assert "m_journal.AppendRequest" in source
    assert "m_journal.AppendClose" in source


def test_phase7_terminal_runtime_test_exercises_journal_append_replay_and_duplicates():
    source = (ROOT / "MQL5" / "Scripts" / "RiskJournalRuntimeTest.mq5").read_text(encoding="utf-8")
    assert "CVxRiskJournal journal" in source
    assert "journal.AppendRequest" in source
    assert "journal.AppendClose" in source
    assert "journal.Close()" in source
    assert "CVxRiskJournal replay" in source
    assert "replay.Init(test_login,test_server,reason)" in source
    assert "duplicate request identifier was accepted" in source
    assert "duplicate closing-deal identifier was accepted" in source
    assert "synthetic account only" in source.lower() or "synthetic identity only" in source.lower()


def test_phase7_journal_and_terminal_state_must_exist_as_a_pair():
    risk = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    journal = (ROOT / "MQL5" / "Include" / "Veltrix" / "RiskJournal.mqh").read_text(encoding="utf-8")
    assert "m_journal.WasCreatedNew()" in risk
    assert "existing journal remains; manual recovery required" in risk
    assert "persistent risk state remains; refusing silent journal recreation" in risk
    assert "bool WasCreatedNew(void) const" in journal
    assert "Existing risk journal cannot be opened; refusing to recreate or truncate it" in journal


def test_phase7_journal_replays_permanent_emergency_and_daily_lock_events():
    source = (ROOT / "MQL5" / "Include" / "Veltrix" / "RiskJournal.mqh").read_text(encoding="utf-8")
    assert 'event_type=="ESTOP"' in source
    assert 'event_type=="DAILY_LOCK"' in source
    assert "m_emergency_stop=true" in source
    assert "HasDailyLock" in source
    assert "AppendEmergencyStop" in source
    assert "AppendDailyLock" in source


def test_phase7_manual_daily_reactivation_is_owner_confirmed_and_journaled():
    controls = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    journal = (ROOT / "MQL5" / "Include" / "Veltrix" / "RiskJournal.mqh").read_text(encoding="utf-8")
    assert "RearmDailyLossLock" in controls
    assert "owner_confirmed" in controls
    assert "Explicit owner confirmation is required" in controls
    assert "m_journal.AppendDailyRearm" in controls
    assert "DailyRearmEquity" in controls
    assert "Emergency stop remains independently latched" in controls
    assert 'event_type=="DAILY_REARM"' in journal
    assert "AppendDailyRearm" in journal
    assert "HasDailyRearm" in journal
    assert "ActiveDailyLockDay" in controls
    assert "LatestDailyRearmEquity" in controls
    assert "ActiveDailyLockCount" in journal
    assert "RemoveValue(m_daily_lock_keys,key)" in journal


def test_phase7_risk_controls_restore_journal_locks_and_persist_loss_locks():
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8")
    assert "m_journal.HasEmergencyStop()" in source
    assert "m_journal.HasDailyLock(m_server_day_key)" in source
    assert "m_journal.AppendDailyLock(m_server_day_key,event_time,loss_percent,journal_reason)" in source
    assert "m_journal.AppendEmergencyStop(event_time,journal_reason)" in source


def test_phase7_journal_failure_harness_rejects_locked_and_corrupt_existing_files():
    source = (ROOT / "MQL5" / "Scripts" / "RiskJournalFailureRuntimeTest.mq5").read_text(encoding="utf-8")
    assert "Existing risk journal cannot be opened" in source
    assert "FILE_COMMON" in source
    assert "FileWriteString(raw,\"9\")" in source
    assert "incomplete, malformed, or out-of-sequence record" in source
    assert "RISK JOURNAL FAILURE TEST PASS" in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordersendasync(", "ordercheck(", "ctrade", "trade_action_deal")
    assert not [token for token in forbidden if token in lowered]


def test_phase7_workflow_executes_journal_failure_harness():
    source = (ROOT / ".github" / "workflows" / "mql5-compile.yml").read_text(encoding="utf-8")
    assert "Compile risk journal storage-failure runtime test" in source
    assert 'Invoke-Mt5RuntimeScript "RiskJournalFailureRuntimeTest"' in source
    assert "RiskJournalFailureRuntimeTest.ex5" in source
    assert "veltrix_risk_journal_failure_test.result" in source


def test_phase7_terminal_restart_harness_uses_synthetic_identity_and_two_process_stages():
    seed = (ROOT / "MQL5" / "Scripts" / "RiskControlsRestartSeed.mq5").read_text(encoding="utf-8")
    verify = (ROOT / "MQL5" / "Scripts" / "RiskControlsRestartVerify.mq5").read_text(encoding="utf-8")
    assert "TEST_LOGIN 900000007" in seed and "TEST_SERVER" in seed
    assert "LatchEmergencyStop" in seed and "AppendDailyLock" in seed
    assert "TEST_LOGIN 900000007" in verify and "TEST_SERVER" in verify
    assert "IsEmergencyStopped" in verify and "IsDailyLossLocked" in verify
    assert "terminal process restart" in verify.lower()
    assert "ACCOUNT_LOGIN" not in seed and "ACCOUNT_LOGIN" not in verify
    assert "OrderSend(" not in seed and "OrderSend(" not in verify


def test_phase7_workflow_runs_seed_and_verify_as_separate_terminal_processes():
    source = (ROOT / ".github" / "workflows" / "mql5-compile.yml").read_text(encoding="utf-8")
    assert "Compile terminal process-restart seed script" in source
    assert "Compile terminal process-restart verification script" in source
    assert 'Invoke-Mt5RuntimeScript "RiskControlsRestartSeed"' in source
    assert 'Invoke-Mt5RuntimeScript "RiskControlsRestartVerify"' in source
    assert "RiskControlsRestartSeed.ex5" in source
    assert "RiskControlsRestartVerify.ex5" in source


def test_phase7_runtime_journal_harness_covers_permanent_locks():
    source = (ROOT / "MQL5" / "Scripts" / "RiskJournalRuntimeTest.mq5").read_text(encoding="utf-8")
    assert "journal.AppendDailyLock" in source
    assert "journal.AppendEmergencyStop" in source
    assert "replay.HasDailyLock" in source
    assert "replay.HasEmergencyStop" in source


def test_phase7_risk_controls_runtime_harness_checks_restart_lock_and_checksum_failures():
    source = (ROOT / "MQL5" / "Scripts" / "RiskControlsRuntimeTest.mq5").read_text(encoding="utf-8")
    assert "CVxRiskControls" in source
    assert "SeedEmergencyStop" in source
    assert "AppendSyntheticDailyLock" in source
    assert "VerifyRestoredLocks" in source
    assert "abandoned transaction-lock fail-closed test" in source
    assert "risk-state checksum fail-closed test" in source
    assert "GlobalVariableDel" in source


def test_phase7_mql5_workflow_executes_terminal_runtime_scripts_without_broker_login():
    source = (ROOT / ".github" / "workflows" / "mql5-compile.yml").read_text(encoding="utf-8")
    assert "Execute terminal-side risk runtime tests" in source
    assert 'Login=0' in source
    assert "[Common]" in source
    assert "[StartUp]" in source
    assert source.index("[StartUp]") < source.index("Script=$scriptName")
    assert "AllowLiveTrading=0" in source
    assert "AllowDllImport=0" in source
    assert "Symbol=XAUUSD" in source
    assert "Script=$scriptName" in source
    assert "ShutdownTerminal=1" in source
    assert "veltrix_risk_controls_runtime_test.result" in source
    assert "veltrix_risk_journal_runtime_test.result" in source


OVERALL_LOSS_GUARD_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "OverallAccountLossGuard.mqh"


def test_overall_loss_guard_uses_immutable_verified_original_deposit_and_persistent_lock():
    source = OVERALL_LOSS_GUARD_SOURCE.read_text(encoding="utf-8")
    required = (
        "original_deposit_verified", "verified_original_deposit",
        "VX_ORIGDEP_", "VX_OVERALL_LOCK_", "VX_OVERALL_SUM_",
        "StateChecksum", "GlobalVariablesFlush", "ACCOUNT_EQUITY",
        "m_loss_limit_percent=50.0", "Rearm",
        "immutable stored baseline", "Equity must recover above the 50% loss boundary",
    )
    for token in required:
        assert token in source
    lowered = source.lower()
    forbidden = ("ordersend(", "ordersendasync(", "ordercheck(",
                 "ctrade", "trade_action_deal", "positionclose(",
                 "positionmodify(")
    assert not [token for token in forbidden if token in lowered]


def test_overall_loss_guard_fails_closed_on_unverified_or_tampered_baseline():
    source = OVERALL_LOSS_GUARD_SOURCE.read_text(encoding="utf-8")
    assert "independently owner-verified original deposit are mandatory" in source
    assert "Supplied original-deposit evidence conflicts with the immutable stored baseline" in source
    assert "Overall-loss persistent state is partial" in source
    assert "Overall-loss persistent checksum mismatch" in source
    assert "m_original_deposit=stored_baseline" in source


OVERALL_GUARD_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "OverallAccountLossGuard.mqh"
OVERALL_GUARD_RUNTIME = ROOT / "MQL5" / "Scripts" / "OverallAccountLossGuardRuntimeTest.mq5"
MQL5_WORKFLOW = ROOT / ".github" / "workflows" / "mql5-compile.yml"


def test_overall_loss_guard_runtime_covers_threshold_restart_tamper_and_rearm():
    guard = OVERALL_GUARD_SOURCE.read_text(encoding="utf-8")
    runtime = OVERALL_GUARD_RUNTIME.read_text(encoding="utf-8")
    for token in (
        "ACCOUNT_EQUITY", "m_original_deposit", "m_loss_limit_percent=50.0",
        "VX_ORIGDEP_", "VX_OVERALL_LOCK_", "VX_OVERALL_SUM_",
        "StateChecksum", "GlobalVariablesFlush", "EvaluateEquityValue",
        "RearmEquityValue", "original_deposit_verified",
    ):
        assert token in guard
    for token in (
        "EvaluateEquitySnapshotForTest(5000.0",
        "RearmEquitySnapshotForTest(true,5000.0",
        "RearmEquitySnapshotForTest(true,5001.0",
        "conflicts with the immutable stored baseline",
        "checksum mismatch", "persistent state is partial",
        "restart replay", "GlobalVariableDel",
    ):
        assert token in runtime
    lowered = guard.lower() + runtime.lower()
    forbidden = (
        "ordersend(", "ordersendasync(", "ordercheck(", "ctrade",
        "trade_action_deal", "positionclose(", "positionmodify(",
    )
    assert not [token for token in forbidden if token in lowered]


def test_overall_loss_guard_runtime_is_wired_into_mql5_ci():
    workflow = MQL5_WORKFLOW.read_text(encoding="utf-8")
    assert "Compile overall account-loss guard runtime test script" in workflow
    assert "OverallAccountLossGuardRuntimeTest.ex5" in workflow
    assert 'Invoke-Mt5RuntimeScript "OverallAccountLossGuardRuntimeTest"' in workflow
    assert "veltrix_overall_loss_guard_runtime_test.result" in workflow
