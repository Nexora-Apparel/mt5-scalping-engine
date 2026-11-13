from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EA = ROOT / "MQL5" / "Experts" / "VeltrixDemoDiagnostics.mq5"
WORKFLOW = ROOT / ".github" / "workflows" / "veltrix-demo-diagnostics.yml"


def test_diagnostic_checks_demo_identity_and_connection():
    source = EA.read_text(encoding="utf-8")
    assert "TERMINAL_CONNECTED" in source
    assert "ACCOUNT_LOGIN" in source
    assert "ACCOUNT_TRADE_MODE" in source
    assert "ACCOUNT_TRADE_MODE_DEMO" in source
    assert "ACCOUNT_SERVER" in source
    assert "ExpectedDemoLogin" in source
    assert "ExpectedDemoServer" in source


def test_diagnostic_resolves_exact_xauusd_contract_and_quote_integrity():
    source = EA.read_text(encoding="utf-8")
    assert "ResolveXauUsdSymbol" in source
    assert 'StringSubstr(upper,0,6)!="XAUUSD"' in source
    assert 'SYMBOL_CURRENCY_BASE' in source and 'SYMBOL_CURRENCY_PROFIT' in source
    assert 'XAGUSD' not in source
    assert "SymbolInfoTick" in source
    assert "SYMBOL_POINT" in source
    assert "tick.time_msc" in source
    assert "QuoteMaxAgeMilliseconds" in source
    assert "MaxSpreadPoints" in source
    assert "StableSamplesRequired" in source


def test_diagnostic_is_read_only_and_contains_no_trade_submission_api():
    source = EA.read_text(encoding="utf-8")
    forbidden = (
        r"\bOrderSend\s*\(",
        r"\bOrderSendAsync\s*\(",
        r"\bCTrade\b",
        r"\bPositionOpen\s*\(",
        r"\bPositionClose\s*\(",
        r"\bBuy\s*\(",
        r"\bSell\s*\(",
        r"\bOrderModify\s*\(",
        r"\bOrderDelete\s*\(",
    )
    for pattern in forbidden:
        assert not re.search(pattern, source), pattern


def test_workflow_disables_trading_and_requires_diagnostic_pass_marker():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "AllowLiveTrading=0" in workflow
    assert "Enabled=1" in workflow
    assert "VELTRIX DEMO DIAGNOSTIC PASSED" in workflow
    assert "VELTRIX DEMO DIAGNOSTIC FAILED" in workflow
    assert "MT5_LOGIN" in workflow
    assert "MT5_PASSWORD" in workflow
    assert "MT5_SERVER" in workflow
