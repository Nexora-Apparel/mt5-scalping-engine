from types import SimpleNamespace

import pytest

from tools import mt5_runtime_metadata_verification as verifier


class FakeMT5:
    __version__ = "5.0.6231"

    def __init__(self, *, dlls_allowed=False, currency_base="XAU", currency_profit="USD"):
        self.info = SimpleNamespace(
            dlls_allowed=dlls_allowed,
            build=5500,
        )
        self.symbol = SimpleNamespace(
            currency_base=currency_base,
            currency_profit=currency_profit,
            point=0.001,
        )
        self.shutdown_called = False

    def initialize(self, *args, **kwargs):
        return True

    def terminal_info(self):
        return self.info

    def symbol_info(self, symbol):
        assert symbol == "XAUUSDm"
        return self.symbol

    def version(self):
        return (500, 5500, "20 Nov 2026")

    def shutdown(self):
        self.shutdown_called = True


@pytest.fixture
def account_helpers(monkeypatch):
    monkeypatch.setattr(
        verifier, "connect_expected_account",
        lambda *args: {"trade_mode": verifier.DEMO_TRADE_MODE},
    )
    monkeypatch.setattr(verifier, "validate_account", lambda *args: None)
    monkeypatch.setattr(verifier, "discover_symbol", lambda *args: "XAUUSDm")


def test_verification_reports_both_fields_and_never_requests_ticks(account_helpers):
    mt5 = FakeMT5()
    result = verifier.verify(mt5, "C:\\MT5\\terminal64.exe", 123, "secret", "Exness-MT5Trial10")

    assert result["status"] == "PASS"
    assert result["dll_imports_runtime_verified"] is True
    assert result["dll_imports_enabled"] is False
    assert result["contract_currency_metadata_verified"] is True
    assert result["instrument_specs"]["XAUUSD"]["currency_base"] == "XAU"
    assert result["instrument_specs"]["XAUUSD"]["currency_profit"] == "USD"
    assert result["ticks_requested"] is False
    assert result["order_submission"] is False
    assert result["position_management"] is False
    assert mt5.shutdown_called is True


@pytest.mark.parametrize("dlls_allowed", [True, None])
def test_verification_fails_closed_when_runtime_dll_state_is_not_false(account_helpers, dlls_allowed):
    mt5 = FakeMT5(dlls_allowed=dlls_allowed)
    with pytest.raises(verifier.DiagnosticFailure, match="DLL imports are disabled"):
        verifier.verify(mt5, "C:\\MT5\\terminal64.exe", 123, "secret", "Exness-MT5Trial10")
    assert mt5.shutdown_called is True


@pytest.mark.parametrize(
    ("currency_base", "currency_profit"),
    [("XAG", "USD"), ("XAU", "EUR"), (None, "USD")],
)
def test_verification_fails_closed_for_wrong_or_missing_contract_currencies(
    account_helpers, currency_base, currency_profit
):
    mt5 = FakeMT5(currency_base=currency_base, currency_profit=currency_profit)
    with pytest.raises(verifier.DiagnosticFailure, match="contract metadata"):
        verifier.verify(mt5, "C:\\MT5\\terminal64.exe", 123, "secret", "Exness-MT5Trial10")
    assert mt5.shutdown_called is True


def test_verification_rejects_non_demo_account(monkeypatch):
    monkeypatch.setattr(
        verifier, "connect_expected_account",
        lambda *args: {"trade_mode": "REAL"},
    )
    mt5 = FakeMT5()
    with pytest.raises(verifier.DiagnosticFailure, match="DEMO account"):
        verifier.verify(mt5, "C:\\MT5\\terminal64.exe", 123, "secret", "Exness-MT5Trial10")
    assert mt5.shutdown_called is True
