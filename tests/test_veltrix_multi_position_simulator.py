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
