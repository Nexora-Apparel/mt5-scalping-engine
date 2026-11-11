from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EA_SOURCE = ROOT / "MQL5" / "Experts" / "VeltrixScalper.mq5"
GUARD_SOURCE = ROOT / "MQL5" / "Include" / "Veltrix" / "MarketGuard.mqh"


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


def test_veltrix_ea_uses_repository_relative_market_guard_include():
    source = EA_SOURCE.read_text(encoding="utf-8")
    assert '#include "..\\Include\\Veltrix\\MarketGuard.mqh"' in source
    assert "EventSetMillisecondTimer" in source
    assert "EventKillTimer" in source
