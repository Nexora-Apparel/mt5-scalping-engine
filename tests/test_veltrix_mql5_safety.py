from pathlib import Path
import math


ROOT = Path(__file__).resolve().parents[1]
EA_SOURCE = ROOT / "MQL5" / "Experts" / "VeltrixScalper.mq5"
GUARD_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "MarketGuard.mqh"
RISK_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "RiskAllocator.mqh"


def test_veltrix_foundation_contains_no_order_submission_api():
    source = EA_SOURCE.read_text(encoding="utf-8").lower()
    forbidden = (
        "ordersend(",
        "ordercheck(",
        "trade_action_deal",
        "trade_action_pending",
        "ctrade",
        "positionopen(",
    )
    assert not [token for token in forbidden if token in source]


def test_market_guard_is_read_only_and_checks_quote_health():
    source = GUARD_SOURCE.read_text(encoding="utf-8")
    required = (
        "SymbolInfoTick",
        "SYMBOL_TRADE_TICK_SIZE",
        "SYMBOL_TRADE_TICK_VALUE_LOSS",
        "SYMBOL_VOLUME_MIN",
        "SYMBOL_VOLUME_STEP",
        "SYMBOL_TRADE_STOPS_LEVEL",
        "SYMBOL_TRADE_FREEZE_LEVEL",
        "TimeTradeServer",
        "GetTickCount64",
        "m_max_spread_points",
        "m_max_quote_age_ms",
    )
    for token in required:
        assert token in source

    lowered = source.lower()
    forbidden = ("ordersend(", "ordercheck(", "trade_action_deal", "ctrade")
    assert not [token for token in forbidden if token in lowered]


def test_veltrix_ea_uses_repository_relative_includes_and_timer():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert r'#include "..\\Include\\Veltrix\\MarketGuard.mqh"' in source
    assert r'#include "..\\Include\\Veltrix\\RiskAllocator.mqh"' in source
    assert "EventSetMillisecondTimer" in source
    assert "EventKillTimer" in source


def test_risk_allocator_is_fail_closed_and_rounds_volume_down():
    source = RISK_SOURCE.read_text(encoding="utf-8")
    required = (
        "VxCalculateRiskVolume",
        "tick_value_loss",
        "current_open_risk_money",
        "max_portfolio_risk_percent",
        "MathFloor",
        "MathIsValidNumber",
        "Non-finite numeric input",
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
    # A $10 balance with these illustrative contract values cannot support
    # the broker minimum at the selected stop distance: must skip, not round up.
    assert _reference_volume(10, 0.25, 2.0, 0.01, 1.0,
                             0.01, 100.0, 0.01, 0.0, 1.0, 0, 3) == 0.0

    # A valid illustrative case rounds down to the broker step.
    assert _reference_volume(1000, 1.0, 0.1, 0.01, 1.0,
                             0.01, 100.0, 0.01, 0.0, 3.0, 0, 3) == 1.0

    # Existing exposure consumes portfolio capacity; new risk must fit only
    # the remaining aggregate budget.
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
