import json
from pathlib import Path

import pytest

from tools.mt5_xauusd_tick_replay import (
    QuoteTick,
    ReplayError,
    evaluate_event,
    replay_events,
    validate_ticks,
)


REGISTRY_PATH = Path("research/xauusd_strategy_registry_v1.json")


@pytest.fixture
def registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def event(direction="long", horizon=5, signal_end=1000):
    return {
        "signal_id": "smoke-001",
        "candidate_id": "XAU_MOMENTUM_CONTINUATION_V1",
        "signal_window_end_msc": signal_end,
        "direction": direction,
        "horizon_seconds": horizon,
    }


def quotes():
    return [
        QuoteTick(1000, 100.000, 100.240),
        QuoteTick(1001, 100.000, 100.240),
        QuoteTick(2000, 100.050, 100.290),
        QuoteTick(6001, 100.500, 100.740),
        QuoteTick(7000, 100.450, 100.690),
    ]


def test_long_uses_ask_entry_and_bid_exit_spread_once():
    result = evaluate_event(quotes(), event(), point_size=0.001, slippage_grid=[0, 1, 2, 5])
    assert result["status"] == "OUTCOME_AVAILABLE"
    assert result["entry_executable_price"] == 100.240
    assert result["exit_executable_price"] == 100.500
    assert result["gross_pnl_price_units"] == pytest.approx(0.260)
    assert result["spread_included_once"] is True
    assert result["slippage_sensitivity"][1]["pnl_before_commission_price_units"] == pytest.approx(0.258)
    assert result["net_after_commission"] is None


def test_short_uses_bid_entry_and_ask_exit():
    result = evaluate_event(quotes(), event(direction="short"), point_size=0.001, slippage_grid=[0])
    assert result["status"] == "OUTCOME_AVAILABLE"
    assert result["entry_executable_price"] == 100.000
    assert result["exit_executable_price"] == 100.740
    assert result["gross_pnl_price_units"] == pytest.approx(-0.740)


def test_entry_quote_must_be_strictly_after_signal_window_end():
    result = evaluate_event(quotes(), event(signal_end=1000), point_size=0.001, slippage_grid=[0])
    assert result["entry_time_msc"] == 1001


def test_entry_quote_timeout_is_explicit():
    ticks = [QuoteTick(1000, 100, 100.2), QuoteTick(7001, 100, 100.2)]
    result = evaluate_event(ticks, event(), point_size=0.001, slippage_grid=[0])
    assert result["status"] == "ENTRY_QUOTE_TIMEOUT"


def test_exit_quote_must_be_within_two_seconds_of_horizon():
    ticks = [QuoteTick(1001, 100, 100.2), QuoteTick(8002, 100.1, 100.3)]
    result = evaluate_event(ticks, event(), point_size=0.001, slippage_grid=[0])
    assert result["status"] == "EXIT_QUOTE_TIMEOUT"


def test_invalid_direction_or_horizon_fails_closed():
    with pytest.raises(ReplayError, match="direction"):
        evaluate_event(quotes(), {**event(), "direction": "buy"}, point_size=0.001, slippage_grid=[0])
    with pytest.raises(ReplayError, match="horizon"):
        evaluate_event(quotes(), {**event(), "horizon_seconds": 10}, point_size=0.001, slippage_grid=[0])


def test_tick_stream_rejects_backwards_timestamps_and_crossed_quotes():
    with pytest.raises(ReplayError, match="nondecreasing"):
        validate_ticks([QuoteTick(2000, 100, 100.2), QuoteTick(1000, 100, 100.2)])
    with pytest.raises(ReplayError, match="invalid bid/ask"):
        validate_ticks([QuoteTick(1000, 100.2, 100.1)])


def test_replay_keeps_commission_unverified_and_execution_disabled(registry):
    ticks = quotes()
    manifest = {
        "account_mode": "DEMO",
        "trading_enabled": False,
        "dll_imports_enabled": False,
        "instrument_specs": {
            "XAUUSD": {
                "broker_symbol": "XAUUSDm",
                "currency_base": "XAU",
                "currency_profit": "USD",
                "point": 0.001,
            }
        },
    }
    result = replay_events(ticks, [event()], manifest, registry)
    assert result["status"] == "PASS"
    assert result["research_only"] is True
    assert result["commission_status"] == "UNVERIFIED_REQUIRED_INPUT"
    assert result["outcomes"][0]["net_after_commission"] is None
    assert result["outcomes"][0]["execution_sent"] is False


def test_replay_rejects_non_demo_or_enabled_trading(registry):
    manifest = {
        "account_mode": "LIVE",
        "trading_enabled": False,
        "dll_imports_enabled": False,
        "instrument_specs": {
            "XAUUSD": {"broker_symbol": "XAUUSDm", "currency_base": "XAU", "currency_profit": "USD", "point": 0.001}
        },
    }
    with pytest.raises(ReplayError, match="DEMO"):
        replay_events(quotes(), [event()], manifest, registry)
