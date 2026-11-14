import pytest

from tools.mt5_xauusd_multi_position_simulator import (
    PortfolioSimulationError,
    PortfolioTick,
    simulate_portfolio,
)


SPEC = {
    "point_size": 0.01,
    "tick_size": 0.01,
    "tick_value_loss": 1.0,
    "volume_min": 0.01,
    "volume_max": 100.0,
    "volume_step": 0.01,
    "margin_per_lot": 100.0,
}
RISK = {
    "equity": 10000.0,
    "risk_per_trade_percent": 0.10,
    "max_portfolio_risk_percent": 0.50,
    "initial_free_margin": 10000.0,
    "margin_reserve_money": 100.0,
}


def ev(signal_id, stamp, *, direction="long", hold=10, stop=0.10, target=0.20):
    return {
        "signal_id": signal_id,
        "candidate_id": "MULTI_POSITION_SYNTHETIC_TEST",
        "signal_window_end_msc": stamp,
        "direction": direction,
        "hold_seconds": hold,
        "stop_distance_price": stop,
        "take_profit_distance_price": target,
    }


def ticks():
    # Quotes are dense enough for the configured five-second freshness gate.
    return [
        PortfolioTick(1000, 100.00, 100.02),
        PortfolioTick(1100, 100.00, 100.02),
        PortfolioTick(2000, 100.01, 100.03),
        PortfolioTick(5000, 100.02, 100.04),
        PortfolioTick(9000, 100.03, 100.05),
        PortfolioTick(11100, 100.04, 100.06),
        PortfolioTick(12000, 100.05, 100.07),
        PortfolioTick(15000, 100.06, 100.08),
        PortfolioTick(20000, 100.07, 100.09),
        PortfolioTick(22000, 100.08, 100.10),
        PortfolioTick(25000, 100.09, 100.11),
        PortfolioTick(30000, 100.10, 100.12),
        PortfolioTick(35000, 100.11, 100.13),
        PortfolioTick(40000, 100.12, 100.14),
    ]


def test_multiple_positions_overlap_without_count_ceiling():
    events = [ev("p1", 1000), ev("p2", 2000), ev("p3", 5000)]
    result = simulate_portfolio(ticks(), events, SPEC, RISK)
    assert result["summary"]["max_concurrent_positions"] == 3
    assert result["summary"]["accepted_positions"] == 3
    assert result["summary"]["max_open_stop_risk_money"] <= 50.0 + 1e-8


def test_aggregate_risk_capacity_rejects_additional_trade_not_position_count():
    risk = {**RISK, "risk_per_trade_percent": 0.25, "max_portfolio_risk_percent": 0.50}
    events = [ev("p1", 1000, stop=0.10), ev("p2", 2000, stop=0.10), ev("p3", 5000, stop=0.10)]
    result = simulate_portfolio(ticks(), events, SPEC, risk)
    assert result["summary"]["accepted_positions"] <= 2
    assert any(item["status"] == "REJECTED_AGGREGATE_RISK" for item in result["trades"])


def test_each_position_obeys_10_to_60_second_deadline():
    result = simulate_portfolio(ticks(), [ev("p1", 1000, hold=10)], SPEC, RISK)
    trade = result["trades"][0]
    assert trade["holding_seconds"] == 10.0
    assert trade["status"] == "TIME_STOP"


def test_stop_loss_triggers_on_executable_side_and_reserves_no_future_risk():
    stream = [
        PortfolioTick(1000, 100.00, 100.02),
        PortfolioTick(1100, 100.00, 100.02),
        PortfolioTick(2000, 99.90, 99.92),
        PortfolioTick(3000, 99.80, 99.82),
    ]
    result = simulate_portfolio(stream, [ev("sl", 1000, stop=0.10)], SPEC, RISK)
    trade = result["trades"][0]
    assert trade["status"] == "STOP_LOSS"
    assert trade["holding_seconds"] == 0.9
    assert trade["gross_pnl_money"] < 0


def test_take_profit_triggers_on_executable_side():
    stream = [
        PortfolioTick(1000, 100.00, 100.02),
        PortfolioTick(1100, 100.00, 100.02),
        PortfolioTick(2000, 100.25, 100.27),
        PortfolioTick(3000, 100.30, 100.32),
    ]
    result = simulate_portfolio(stream, [ev("tp", 1000, target=0.20)], SPEC, RISK)
    assert result["trades"][0]["status"] == "TAKE_PROFIT"
    assert result["trades"][0]["gross_pnl_money"] > 0


def test_margin_reserve_blocks_new_position():
    risk = {**RISK, "initial_free_margin": 150.0, "margin_reserve_money": 100.0}
    result = simulate_portfolio(ticks(), [ev("p1", 1000)], SPEC, risk)
    assert result["trades"][0]["status"] == "REJECTED_MARGIN_RESERVE"


def test_data_gap_leaves_position_unresolved_and_risk_reserved():
    stream = [
        PortfolioTick(1000, 100.00, 100.02),
        PortfolioTick(1100, 100.00, 100.02),
        PortfolioTick(8000, 100.00, 100.02),
    ]
    result = simulate_portfolio(stream, [ev("gap", 1000)], SPEC, RISK)
    assert result["trades"][0]["status"] == "DATA_GAP_UNRESOLVED"
    assert result["summary"]["unresolved_positions_at_end"] == 1


def test_unknown_exit_does_not_release_aggregate_risk():
    stream = [
        PortfolioTick(1000, 100.00, 100.02),
        PortfolioTick(1100, 100.00, 100.02),
        PortfolioTick(8000, 100.00, 100.02),
        PortfolioTick(9000, 100.00, 100.02),
    ]
    events = [ev(f"p{i}", 1000) for i in range(1, 7)]
    result = simulate_portfolio(stream, events, SPEC, RISK)
    assert result["trades"][0]["status"] == "DATA_GAP_UNRESOLVED"
    assert result["trades"][-1]["status"] == "REJECTED_AGGREGATE_RISK"


def test_commission_stays_unverified_and_net_pnl_is_never_claimed():
    result = simulate_portfolio(ticks(), [ev("p1", 1000)], SPEC, RISK)
    assert result["commission_status"] == "UNVERIFIED_REQUIRED_INPUT"
    assert result["net_performance_allowed"] is False
    assert result["trades"][0]["net_pnl_money"] is None


@pytest.mark.parametrize("hold", [0, 9, 61, True])
def test_invalid_hold_duration_fails_closed(hold):
    with pytest.raises(PortfolioSimulationError, match="hold_seconds"):
        simulate_portfolio(ticks(), [ev("bad", 1000, hold=hold)], SPEC, RISK)


def test_risk_and_margin_inputs_fail_closed():
    with pytest.raises(PortfolioSimulationError, match="hard ceilings"):
        simulate_portfolio(ticks(), [ev("p1", 1000)], SPEC, {**RISK, "risk_per_trade_percent": 0.30})
    with pytest.raises(PortfolioSimulationError, match="margin_per_lot"):
        simulate_portfolio(ticks(), [ev("p1", 1000)], {k: v for k, v in SPEC.items() if k != "margin_per_lot"}, RISK)


def test_slippage_is_applied_adversely_on_both_sides():
    no_slip = simulate_portfolio(ticks(), [ev("base", 1000)], SPEC, RISK, slippage_points_per_side=0)
    with_slip = simulate_portfolio(ticks(), [ev("slip", 1000)], SPEC, RISK, slippage_points_per_side=2)
    assert with_slip["trades"][0]["gross_pnl_money"] < no_slip["trades"][0]["gross_pnl_money"]
