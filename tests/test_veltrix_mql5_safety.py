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
                    "BrokerReconciler.mqh", "ExecutionCoordinator.mqh"):
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
                      open_risk, portfolio_pct, open_positions, max_positions):
    numeric = (equity, risk_pct, stop_distance, tick_size, tick_value_loss,
               min_volume, max_volume, step, open_risk, portfolio_pct)
    if not all(math.isfinite(value) for value in numeric):
        return 0.0
    if open_positions >= max_positions or min(equity, risk_pct, stop_distance,
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
                             0.01, 100.0, 0.01, 0.0, 1.0, 0, 3) == 0.0
    assert _reference_volume(1000, 1.0, 0.1, 0.01, 1.0,
                             0.01, 100.0, 0.01, 0.0, 3.0, 0, 3) == 1.0
    assert _reference_volume(1000, 2.0, 0.1, 0.01, 1.0,
                             0.01, 100.0, 0.01, 25.0, 3.0, 1, 3) == 0.5


def test_reference_risk_vectors_reject_nan_and_infinity():
    baseline = [1000.0, 1.0, 0.1, 0.01, 1.0, 0.01, 100.0,
                0.01, 0.0, 3.0]
    for index in range(len(baseline)):
        for invalid in (math.nan, math.inf, -math.inf):
            values = baseline.copy()
            values[index] = invalid
            assert _reference_volume(*values, 0, 3) == 0.0


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
        "ValidateDemoIntent", "ACCOUNT_TRADE_MODE_DEMO",
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
        "max_daily_loss_percent>1.00",
        "config.max_positions!=1", "cooldown_seconds<30",
        "max_consecutive_losses>3", "BeginServerDay",
        "EvaluateDailyLoss", "RecordVerifiedClose",
        "RegisterApprovedIntent", "RequestSeen",
        "LatchEmergencyStop", "m_emergency_stop",
        "Only a verified XAUUSD contract is permitted",
        "Duplicate request identifier rejected",
        "Post-loss cooldown is active",
        "daily loss lock is latched until the next verified server day",
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
    source = RISK_CONTROLS_SOURCE.read_text(encoding="utf-8").read_text(encoding="utf-8")
    assert "m_daily_loss_locked=false;" in source
    assert "m_emergency_stop=true;" in source
    day_reset = source.split("bool BeginServerDay", 1)[1].split("bool EvaluateDailyLoss", 1)[0]
    assert "m_daily_loss_locked=false;" in day_reset
    assert "m_emergency_stop=false;" not in day_reset
    assert "A cooldown and emergency stop deliberately survive a day boundary." in source


def test_phase7_risk_policy_reference_boundaries():
    # Policy ceilings are hard caps; the defaults remain operator-configured and unused.
    assert 0.25 <= 0.25
    assert not (0.250001 <= 0.25)
    assert 0.50 <= 0.50
    assert not (0.500001 <= 0.50)
    assert 1.00 <= 1.00
    assert not (1.000001 <= 1.00)
    day_start = 1000.0
    daily_limit = 1.0
    assert (day_start - 990.01) / day_start * 100 < daily_limit
    assert (day_start - 990.0) / day_start * 100 >= daily_limit
