import csv
import hashlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "mt5_xauusd_historical_tick_probe.py"
spec = importlib.util.spec_from_file_location("historical_probe", PATH)
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


def test_parse_utc_requires_timezone():
    assert probe_module.parse_utc("2026-11-13T12:00:00Z").tzinfo == timezone.utc
    with pytest.raises(ValueError, match="include Z"):
        probe_module.parse_utc("2026-11-13T12:00:00")


class FakeHistoricalMT5:
    COPY_TICKS_ALL = 3

    def __init__(self):
        self.shutdown_called = False

    def initialize(self, *args, **kwargs):
        return True

    def symbol_select(self, symbol, enabled):
        return symbol == "XAUUSDm" and enabled

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01) if symbol == "XAUUSDm" else None

    def copy_ticks_range(self, symbol, start, end, flags):
        assert symbol == "XAUUSDm" and flags == self.COPY_TICKS_ALL
        return [SimpleNamespace(time_msc=1794564000000, bid=3000.0, ask=3000.2,
                                last=3000.1, volume=1.0, volume_real=1.0, flags=3)]

    def last_error(self):
        return (1, "fake")

    def shutdown(self):
        self.shutdown_called = True


def test_historical_probe_is_demo_read_only_and_hashes_output(tmp_path, monkeypatch):
    api = FakeHistoricalMT5()
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "not-a-real-password")
    monkeypatch.setenv("MT5_SERVER", "Exness-MT5Trial")
    monkeypatch.setattr(probe_module, "connect_expected_account",
                        lambda *a, **k: {"trade_mode": probe_module.DEMO_TRADE_MODE})
    monkeypatch.setattr(probe_module, "discover_symbol", lambda *a, **k: "XAUUSDm")
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    end = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
    result = probe_module.probe(api, start, end, tmp_path)
    assert api.shutdown_called
    assert result["status"] == "PASS"
    assert result["account_mode"] == "DEMO"
    assert result["trading_enabled"] is False
    assert result["order_submission"] is False
    assert result["position_management"] is False
    data = (tmp_path / result["csv_file"]).read_bytes()
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    rows = list(csv.DictReader((tmp_path / result["csv_file"]).open(encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["canonical_symbol"] == "XAUUSD"


def test_historical_probe_rejects_empty_interval():
    api = FakeHistoricalMT5()
    start = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
    with pytest.raises(Exception, match="valid increasing UTC interval"):
        probe_module.probe(api, start, start, Path("unused"))
    assert not api.shutdown_called
