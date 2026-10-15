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


def test_daily_loss_baseline_uses_server_day_history_and_fails_closed():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "HistorySelect(dayStart, now)" in source
    assert "AccountInfoDouble(ACCOUNT_BALANCE) - netBalanceChanges" in source
    assert 'Print("Nexora risk gate: cannot select today\'s account history.")' in source
    assert "if(startBalance <= 0.0) return true;" in source


def test_order_requests_remain_behind_fail_closed_gates():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "bool sent = OrderSend(request, result);" in source
    assert "if(!EnableDemoOrders || EmergencyStop)" in source
    assert "return AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;" in source
    assert "if(!SafetyGatesPass())" in source


def test_strategy_tester_uses_isolated_simulated_risk_state():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "bool inTester = (bool)MQLInfoInteger(MQL_TESTER);" in source
    assert "double testerDayStartBalance = 0.0;" in source
    assert "datetime testerDayStartTime = 0;" in source


def test_position_sizing_prefers_loss_side_tick_value():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "SYMBOL_TRADE_TICK_VALUE_LOSS" in source
    assert "if(tickValue <= 0.0)" in source

def test_daily_loss_lockout_latches_until_next_server_day():
    source = EA_PATH.read_text(encoding="utf-8")
    assert "bool testerDailyLossLocked = false;" in source
    assert "GlobalVariableCheck(dailyLossLockKey)" in source
    assert "GlobalVariableSet(dailyLossLockKey, 1.0)" in source
    assert "testerDailyLossLocked = false;" in source
    assert "Once breached, the daily limit stays latched until the next server day." in source
