from __future__ import annotations

import pytest

from tools.mt5_xauusd_multi_position_simulator import (
    PortfolioSimulationError,
    PortfolioTick,
    simulate_portfolio,
)


BROKER = {
    "point_size": 0.01,
    "tick_size": 0.01,
    "tick_value_loss": 1.0,
    "tick_value_profit": 1.0,
    "volume_min": 0.01,
    "volume_max": 100.0,
    "volume_step": 0.001,
    "margin_per_lot": 100.0,
}


def risk_config(*, equity: float = 10000.0, original_deposit: float = 10000.0) -> dict:
    return {
        "equity": equity,
        "original_deposit": original_deposit,
        "original_deposit_verified": True,
        "risk_per_trade_percent": 0.25,
        "max_portfolio_risk_percent": 0.50,
        "initial_free_margin": 10000.0,
        "margin_reserve_money": 100.0,
        "max_daily_loss_percent": 15.0,
        "max_overall_account_loss_percent": 50.0,
    }


def test_simulator_requires_owner_verified_original_deposit():
    config = risk_config()
    config["original_deposit_verified"] = False
    with pytest.raises(PortfolioSimulationError, match="owner-verified"):
        simulate_portfolio(
            [PortfolioTick(1000, 2000.0, 2000.02)],
            [],
            BROKER,
            config,
        )


def test_overall_loss_boundary_blocks_new_positions_independently_of_daily_loss():
    ticks = [
        PortfolioTick(1000, 2000.0, 2000.02),
        PortfolioTick(1100, 2000.0, 2000.02),
    ]
    events = [{
        "signal_id": "already-breached",
        "signal_window_end_msc": 1000,
        "direction": "long",
        "hold_seconds": 15,
        "stop_distance_price": 0.5,
        "take_profit_distance_price": 0.5,
    }]
    result = simulate_portfolio(
        ticks, events, BROKER,
        risk_config(equity=4900.0, original_deposit=10000.0),
    )
    assert result["trades"][0]["status"] == "REJECTED_OVERALL_LOSS_LOCK"
    assert result["summary"]["overall_loss_locked"] is True
    assert result["summary"]["overall_drawdown_percent_at_end"] == pytest.approx(51.0)
    assert result["summary"]["accepted_positions"] == 0


def test_risk_sizing_recalculates_from_marked_equity_after_realized_profit():
    ticks = [
        PortfolioTick(1000, 2000.00, 2000.02),
        PortfolioTick(1100, 2000.00, 2000.02),
        PortfolioTick(1200, 2000.53, 2000.55),
        PortfolioTick(1300, 2000.53, 2000.55),
        PortfolioTick(1400, 2000.53, 2000.55),
        PortfolioTick(6400, 2000.53, 2000.55),
        PortfolioTick(11400, 2000.53, 2000.55),
        PortfolioTick(16400, 2000.53, 2000.55),
    ]
    events = [
        {
            "signal_id": "first-winner",
            "candidate_id": "test",
            "signal_window_end_msc": 1000,
            "direction": "long",
            "hold_seconds": 15,
            "stop_distance_price": 0.5,
            "take_profit_distance_price": 0.5,
        },
        {
            "signal_id": "second-position",
            "candidate_id": "test",
            "signal_window_end_msc": 1300,
            "direction": "long",
            "hold_seconds": 15,
            "stop_distance_price": 0.5,
            "take_profit_distance_price": 0.5,
        },
    ]
    result = simulate_portfolio(ticks, events, BROKER, risk_config())
    first, second = result["trades"]
    assert first["status"] == "TAKE_PROFIT"
    assert second["equity_at_entry"] > 10000.0
    assert second["risk_budget_at_entry_money"] > 25.0
    assert second["volume"] > first["volume"]
    assert result["risk_config"]["overall_account_loss_enforcement"] == "IMPLEMENTED_RESEARCH_ONLY"
    assert all(trade["net_pnl_money"] is None for trade in result["trades"])
    assert result["net_performance_allowed"] is False


def test_aggregate_risk_caps_overlapping_positions_without_a_position_count_cap():
    ticks = [
        PortfolioTick(1000, 2000.00, 2000.00),
        PortfolioTick(1100, 2000.00, 2000.00),
        PortfolioTick(6100, 2000.00, 2000.00),
        PortfolioTick(11100, 2000.00, 2000.00),
        PortfolioTick(16100, 2000.00, 2000.00),
    ]
    events = [
        {
            "signal_id": f"overlap-{index}",
            "signal_window_end_msc": 1000 + index,
            "direction": "long",
            "hold_seconds": 15,
            "stop_distance_price": 0.5,
            "take_profit_distance_price": 5.0,
        }
        for index in range(3)
    ]
    result = simulate_portfolio(ticks, events, BROKER, risk_config())
    assert [trade["status"] for trade in result["trades"]] == [
        "TIME_STOP", "TIME_STOP", "REJECTED_AGGREGATE_RISK"
    ]
    assert result["summary"]["max_concurrent_positions"] == 2
    assert result["summary"]["max_open_stop_risk_money"] <= 50.0 + 1e-8


def test_slippage_sensitivity_never_improves_gross_result_on_flat_quotes():
    ticks = [
        PortfolioTick(1000, 2000.00, 2000.02),
        PortfolioTick(1100, 2000.00, 2000.02),
        PortfolioTick(6100, 2000.00, 2000.02),
        PortfolioTick(11100, 2000.00, 2000.02),
        PortfolioTick(16100, 2000.00, 2000.02),
    ]
    event = [{
        "signal_id": "slippage-stress",
        "signal_window_end_msc": 1000,
        "direction": "long",
        "hold_seconds": 15,
        "stop_distance_price": 0.5,
        "take_profit_distance_price": 5.0,
    }]
    pnl = []
    for points in (0, 1, 2, 5):
        result = simulate_portfolio(
            ticks, event, BROKER, risk_config(),
            slippage_points_per_side=points,
        )
        pnl.append(result["trades"][0]["gross_pnl_money"])
    assert pnl == sorted(pnl, reverse=True)
    assert all(value is not None for value in pnl)


def test_simulator_rejects_mixed_portfolio_configurations():
    ticks = [
        PortfolioTick(1000, 2000.0, 2000.02),
        PortfolioTick(1100, 2000.0, 2000.02),
    ]
    events = [
        {
            "signal_id": "config-a",
            "portfolio_config_id": "sl1_rr1_h15",
            "signal_window_end_msc": 1000,
            "direction": "long",
            "hold_seconds": 15,
            "stop_distance_price": 0.5,
            "take_profit_distance_price": 0.5,
        },
        {
            "signal_id": "config-b",
            "portfolio_config_id": "sl2_rr1_h15",
            "signal_window_end_msc": 1000,
            "direction": "long",
            "hold_seconds": 15,
            "stop_distance_price": 1.0,
            "take_profit_distance_price": 1.0,
        },
    ]
    with pytest.raises(PortfolioSimulationError, match="simulated separately"):
        simulate_portfolio(ticks, events, BROKER, risk_config())
