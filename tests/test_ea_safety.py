from pathlib import Path


EA_PATH = Path(__file__).parents[1] / "MQL5" / "Experts" / "NexoraScalper.mq5"


def test_expert_advisor_defaults_are_fail_closed():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "input bool   EnableDemoOrders       = false;" in source
    assert "input bool   EmergencyStop          = true;" in source
    assert "return AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;" in source
    assert "if(!EnableDemoOrders || EmergencyStop)" in source


def test_expert_advisor_contains_required_risk_gates():
    source = EA_PATH.read_text(encoding="utf-8")
    required_controls = [
        "RiskPercentPerTrade",
        "MaxDailyLossPercent",
        "SpreadIsAcceptable",
        "StopLossPoints",
        "TakeProfitPoints",
        "HasPositionForSymbol",
        "CooldownSeconds",
        "DailyLossLimitReached",
    ]
    for control in required_controls:
        assert control in source
