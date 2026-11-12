from pathlib import Path
from mt5_scalping.config import Settings
from tools.mt5_python_readonly_diagnostic import CANONICAL_SYMBOLS
from tools.dataset_integrity import SYMBOLS
from tools.mt5_tick_market_profile import EXPECTED

ROOT = Path(__file__).resolve().parents[1]


def test_all_python_ingestion_and_analysis_allowlists_are_gold_only():
    assert CANONICAL_SYMBOLS == ("XAUUSD",)
    assert SYMBOLS == {"XAUUSD"}
    assert EXPECTED == ("XAUUSD",)


def test_settings_reject_any_non_gold_symbol():
    assert Settings(_env_file=None).symbols == "XAUUSD"
    for symbol in ("XAGUSD", "EURUSD", "BTCUSD", "XAUUSD,XAGUSD"):
        try:
            Settings(_env_file=None, symbols=symbol)
        except ValueError:
            continue
        raise AssertionError(f"out-of-scope symbol accepted: {symbol}")


def test_mql5_market_and_ai_modules_fail_closed_outside_gold():
    market = (ROOT / "MQL5/Include/Veltrix/MarketGuard.mqh").read_text()
    strategy = (ROOT / "MQL5/Include/Veltrix/StrategyResearch.mqh").read_text()
    collector = (ROOT / "MQL5/Include/Veltrix/FeatureCollector.mqh").read_text()
    exporter = (ROOT / "MQL5/Include/Veltrix/FeatureDatasetExporter.mqh").read_text()
    pipeline = (ROOT / "MQL5/Include/Veltrix/FeaturePipeline.mqh").read_text()
    assert 'base=="XAU" && profit=="USD"' in market
    assert 'config.symbol!="XAUUSD"' in strategy
    assert 'config.symbol!="XAUUSD"' in collector
    assert 'snapshot.symbol!="XAUUSD"' in exporter
    assert "IsVerifiedXauContract(broker_symbol)" in pipeline
    assert 'm_collector.PushQuote("XAUUSD"' in pipeline
    assert "XAGUSD is disabled" in strategy
    assert "XAGUSD is not accepted" in exporter


def test_product_docs_declare_xauusd_only():
    assert "XAUUSD-only" in (ROOT / "README.md").read_text()
    scope = (ROOT / "docs/INSTRUMENT_SCOPE.md").read_text()
    assert "XAUUSD" in scope and "XAGUSD" in scope


def test_legacy_ea_is_also_locked_to_verified_gold_contract():
    legacy = (ROOT / "MQL5/Experts/NexoraScalper.mq5").read_text()
    assert 'StringSubstr(normalized_symbol, 0, 6) != "XAUUSD"' in legacy
    assert 'base_currency != "XAU" || profit_currency != "USD"' in legacy
