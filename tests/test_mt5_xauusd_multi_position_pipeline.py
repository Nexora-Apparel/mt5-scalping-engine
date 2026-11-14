from datetime import datetime, timezone

from tools.mt5_xauusd_multi_position_event_adapter import build_multi_position_events
from tools.mt5_xauusd_multi_position_simulator import PortfolioTick, simulate_portfolio


def test_candidate_to_multi_position_portfolio_pipeline_end_to_end():
    start = 1_800_000_000_000
    rows = []
    for i in range(20):
        rows.append({
            "window_start_utc": datetime.fromtimestamp(start / 1000 + i * 5, timezone.utc).isoformat(),
            "realized_volatility_bps": 2.0,
            "mid_close": 100.0,
        })
    features = {
        "status": "PASS", "research_only": True, "canonical_symbol": "XAUUSD",
        "source_sha256": "c" * 64, "features": rows,
    }
    candidate_events = {
        "status": "PASS", "research_only": True, "canonical_symbol": "XAUUSD",
        "source_sha256": "c" * 64, "data_role": "DEVELOPMENT_ONLY",
        "events": [{
            "signal_id": "candidate-01", "candidate_id": "MOMENTUM_TEST",
            "signal_window_index": 12, "signal_window_end_msc": start + 13 * 5000,
            "direction": "long", "horizon_seconds": 15,
            "parameters": {"lookback_seconds": 10},
        }],
    }
    broker = {
        "account_mode": "DEMO", "trading_enabled": False,
        "instrument_specs": {"XAUUSD": {
            "point_size": 0.01, "tick_size": 0.01,
            "stops_level_points": 10, "tick_value_loss": 1.0,
            "tick_value_profit": 1.0, "volume_min": 0.01,
            "volume_max": 100.0, "volume_step": 0.01,
            "margin_per_lot": 100.0,
        }},
    }
    policy = {
        "status": "PREREGISTERED_RESEARCH_ONLY", "execution_enabled": False,
        "holding_seconds": [15],
        "stop_volatility_multipliers": [1.0],
        "take_profit_reward_r_multiples": [1.0],
    }
    adapted = build_multi_position_events(features, candidate_events, broker, policy)
    assert adapted["event_count"] == 1

    signal_end = start + 13 * 5000
    ticks = [
        PortfolioTick(signal_end + 100, 100.00, 100.02),
        PortfolioTick(signal_end + 5000, 100.00, 100.02),
        PortfolioTick(signal_end + 10000, 100.00, 100.02),
        PortfolioTick(signal_end + 15100, 100.00, 100.02),
    ]
    risk = {
        "equity": 10000.0, "risk_per_trade_percent": 0.10,
        "max_portfolio_risk_percent": 0.50,
        "max_daily_loss_percent": 1.0,
        "initial_free_margin": 10000.0, "margin_reserve_money": 100.0,
    }
    report = simulate_portfolio(ticks, adapted["events"], broker["instrument_specs"]["XAUUSD"], risk)
    assert report["summary"]["accepted_positions"] == 1
    assert report["trades"][0]["status"] == "TIME_STOP"
    assert report["trades"][0]["holding_seconds"] == 15.0
    assert report["trades"][0]["execution_sent"] is False
    assert report["trades"][0]["net_pnl_money"] is None
    assert report["commission_status"] == "UNVERIFIED_REQUIRED_INPUT"
