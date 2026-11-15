import pytest

from tools.mt5_xauusd_multi_position_robustness import (
    RobustnessEvaluationError,
    run_robustness_sweep,
)
from tools.mt5_xauusd_multi_position_simulator import PortfolioTick


SPEC = {
    "point_size": 0.01,
    "tick_size": 0.01,
    "tick_value_loss": 1.0,
    "tick_value_profit": 1.0,
    "volume_min": 0.01,
    "volume_max": 100.0,
    "volume_step": 0.01,
    "margin_per_lot": 100.0,
    "currency_base": "XAU",
    "currency_profit": "USD",
    "contract_size": 100.0,
}
RISK = {
    "equity": 10000.0,
    "original_deposit": 10000.0,
    "original_deposit_verified": True,
    "risk_per_trade_percent": 0.10,
    "max_portfolio_risk_percent": 0.50,
    "initial_free_margin": 10000.0,
    "margin_reserve_money": 100.0,
}
TICKS = [
    PortfolioTick(1000, 100.00, 100.02),
    PortfolioTick(1100, 100.00, 100.02),
    PortfolioTick(3000, 100.01, 100.03),
    PortfolioTick(6000, 100.02, 100.04),
    PortfolioTick(9000, 100.03, 100.05),
    PortfolioTick(11100, 100.04, 100.06),
    PortfolioTick(12000, 100.04, 100.06),
]
BROKER = {
    "account_mode": "DEMO",
    "trading_enabled": False,
    "account_identity": {
        "broker": "Exness", "company": "Exness Technologies Ltd",
        "server": "Exness-MT5Trial", "account_mode": "DEMO",
        "account_currency": "USD", "login_hmac_sha256": "c" * 64,
    },
    "instrument_specs": {"XAUUSD": SPEC},
}


def payload():
    return {
        "status": "PASS",
        "research_only": True,
        "schema": "VELTRIX_XAUUSD_MULTI_POSITION_EVENTS_V1",
        "source_sha256": "a" * 64,
        "policy_sha256": "b" * 64,
        "broker_account_identity": dict(BROKER["account_identity"]),
        "data_role": "DEVELOPMENT_ONLY",
        "final_holdout_eligible": False,
        "events": [
            {
                "signal_id": "signal-a",
                "candidate_id": "MOMENTUM",
                "portfolio_config_id": "sl1_rr1_h15",
                "signal_window_end_msc": 1000,
                "direction": "long",
                "hold_seconds": 10,
                "stop_distance_price": 0.5,
                "take_profit_distance_price": 0.5,
                "execution_authorized": False,
            },
            {
                "signal_id": "signal-b",
                "candidate_id": "MOMENTUM",
                "portfolio_config_id": "sl2_rr1_h15",
                "signal_window_end_msc": 1000,
                "direction": "short",
                "hold_seconds": 10,
                "stop_distance_price": 0.5,
                "take_profit_distance_price": 0.5,
                "execution_authorized": False,
            },
        ],
    }


def test_robustness_sweep_isolates_configs_and_runs_all_slippage_cases():
    result = run_robustness_sweep(TICKS, payload(), BROKER, RISK)
    assert result["candidate_configuration_count"] == 2
    assert result["scenario_count"] == 8
    assert {row["portfolio_config_id"] for row in result["scenarios"]} == {
        "sl1_rr1_h15", "sl2_rr1_h15"
    }
    assert {row["slippage_points_per_side"] for row in result["scenarios"]} == {0, 1, 2, 5}
    assert all(row["execution_sent"] is False for row in result["scenarios"])
    assert all(row["net_pnl_money"] is None for row in result["scenarios"])
    assert result["net_performance_allowed"] is False
    assert result["no_trade_benchmark_gross_pnl_money"] == 0.0


def test_robustness_sweep_rejects_unverified_or_holdout_event_payloads():
    invalid = payload()
    invalid["final_holdout_eligible"] = True
    with pytest.raises(RobustnessEvaluationError, match="not final-holdout"):
        run_robustness_sweep(TICKS, invalid, BROKER, RISK)

    invalid = payload()
    invalid["data_role"] = "UNCLASSIFIED_NOT_HOLDOUT"
    with pytest.raises(RobustnessEvaluationError, match="data roles"):
        run_robustness_sweep(TICKS, invalid, BROKER, RISK)


def test_robustness_sweep_rejects_non_demo_or_execution_enabled_snapshots():
    invalid = {**BROKER, "trading_enabled": True}
    with pytest.raises(RobustnessEvaluationError, match="DEMO"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)


@pytest.mark.parametrize("patch", [
    {"broker": "OtherBroker"},
    {"company": "Unrelated Markets"},
    {"server": "Demo-Server"},
    {"account_mode": "REAL"},
    {"account_currency": "EUR"},
    {"login_hmac_sha256": "not-a-sha256"},
    {"login_hmac_sha256": "d" * 63},
])
def test_robustness_sweep_rejects_incomplete_or_mismatched_account_identity(patch):
    invalid = {**BROKER, "account_identity": {**BROKER["account_identity"], **patch}}
    with pytest.raises(RobustnessEvaluationError, match="account identity"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)


def test_robustness_sweep_rejects_missing_account_identity():
    invalid = {key: value for key, value in BROKER.items() if key != "account_identity"}
    with pytest.raises(RobustnessEvaluationError, match="account_identity"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)


@pytest.mark.parametrize("instrument_specs", [None, [], "invalid"])
def test_robustness_sweep_rejects_malformed_instrument_specs(instrument_specs):
    invalid = {**BROKER, "instrument_specs": instrument_specs}
    with pytest.raises(RobustnessEvaluationError, match="instrument_specs"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)


def test_robustness_sweep_rejects_missing_xauusd_instrument_spec():
    invalid = {**BROKER, "instrument_specs": {}}
    with pytest.raises(RobustnessEvaluationError, match="XAUUSD instrument economics"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)


def test_robustness_sweep_rejects_event_snapshot_identity_mismatch():
    events = payload()
    events["broker_account_identity"]["server"] = "Exness-DifferentServer"
    with pytest.raises(RobustnessEvaluationError, match="does not match"):
        run_robustness_sweep(TICKS, events, BROKER, RISK)


def test_robustness_sweep_rejects_missing_candidate_config_or_execution_flag():
    invalid = payload()
    invalid["events"][0]["portfolio_config_id"] = ""
    with pytest.raises(RobustnessEvaluationError, match="configuration"):
        run_robustness_sweep(TICKS, invalid, BROKER, RISK)

    invalid = payload()
    invalid["events"][0]["execution_authorized"] = True
    with pytest.raises(RobustnessEvaluationError, match="prohibit execution"):
        run_robustness_sweep(TICKS, invalid, BROKER, RISK)


def test_robustness_sweep_rejects_duplicate_or_invalid_slippage_grid():
    with pytest.raises(RobustnessEvaluationError, match="duplicates"):
        run_robustness_sweep(TICKS, payload(), BROKER, RISK, slippage_grid=(0, 0))
    with pytest.raises(RobustnessEvaluationError, match="nonnegative"):
        run_robustness_sweep(TICKS, payload(), BROKER, RISK, slippage_grid=(0, -1))

@pytest.mark.parametrize("patch", [
    {"currency_base": "EUR"},
    {"currency_profit": "EUR"},
    {"contract_size": 0},
    {"contract_size": "invalid"},
])
def test_robustness_sweep_rejects_invalid_xauusd_contract_economics(patch):
    invalid = {**BROKER, "instrument_specs": {"XAUUSD": {**SPEC, **patch}}}
    with pytest.raises(RobustnessEvaluationError, match="contract|currency"):
        run_robustness_sweep(TICKS, payload(), invalid, RISK)
