import pytest

from mt5_scalping.config import Settings


def test_execution_disabled_by_default():
    settings = Settings(_env_file=None)
    assert settings.trading_mode == "disabled"
    assert settings.allow_order_submission is False
    assert settings.allow_live_trading is False
    assert settings.execution_enabled is False
    assert settings.symbols == "XAUUSD"


def test_missing_credentials_prevent_execution():
    settings = Settings(
        _env_file=None,
        trading_mode="demo",
        allow_order_submission=True,
        allow_live_trading=False,
        metaapi_token="",
        metaapi_account_id="",
    )
    assert settings.execution_enabled is False


def test_live_trading_never_enabled_by_scaffold():
    settings = Settings(
        _env_file=None,
        trading_mode="demo",
        allow_order_submission=True,
        allow_live_trading=True,
        metaapi_token="example-token",
        metaapi_account_id="example-account",
    )
    assert settings.execution_enabled is False


@pytest.mark.parametrize("symbol", ["XAGUSD", "EURUSD", "BTCUSD", "XAUUSD,XAGUSD", "GOLD"])
def test_non_gold_symbols_are_rejected(symbol):
    with pytest.raises(ValueError, match="XAUUSD only"):
        Settings(_env_file=None, symbols=symbol)


def test_xauusd_is_case_and_whitespace_normalized():
    assert Settings(_env_file=None, symbols=" xauusd ").symbols == "XAUUSD"
