import csv
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "mt5_xauusd_demo_execution_cost_collector.py"
spec = importlib.util.spec_from_file_location("mt5_xauusd_demo_execution_cost_collector", SOURCE)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class FakeMT5:
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT_BY = 3
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(self, deals):
        self.deals = deals
        self.shutdown_called = False

    def initialize(self, *args, **kwargs):
        return True

    def terminal_info(self):
        return SimpleNamespace(connected=True, trade_allowed=False, dlls_allowed=False)

    def account_info(self):
        return SimpleNamespace(login=12345678, server="Exness-MT5Trial", trade_mode=0,
                               company="Exness", currency="USD")

    def symbols_get(self):
        return [SimpleNamespace(name="XAUUSDm", currency_base="XAU", currency_profit="USD")]

    def symbol_select(self, symbol, enabled):
        return symbol == "XAUUSDm" and enabled

    def symbol_info(self, symbol):
        assert symbol == "XAUUSDm"
        return SimpleNamespace(currency_base="XAU", currency_profit="USD",
            trade_contract_size=100.0, point=0.01, digits=2, trade_tick_size=0.01,
            trade_tick_value=1.0, volume_min=0.01, volume_max=200.0, volume_step=0.01)

    def history_deals_get(self, start, end):
        return self.deals

    def last_error(self):
        return (1, "fake")

    def shutdown(self):
        self.shutdown_called = True


def deal(entry, ticket_time, commission, *, position=998877, volume=0.1, price=3000.0):
    return SimpleNamespace(
        symbol="XAUUSDm", position_id=position, time_msc=ticket_time,
        entry=entry, type=0 if entry == 0 else 1, volume=volume, price=price,
        commission=commission, fee=0.0, swap=0.0, profit=1.25,
        ticket=987654321, order=123456789, comment="must-not-export",
    )


def configure(monkeypatch):
    for key, value in {
        "MT5_LOGIN": "12345678", "MT5_PASSWORD": "fake",
        "MT5_SERVER": "Exness-MT5Trial", "MT5_TERMINAL": r"C:\MT5\terminal64.exe",
    }.items():
        monkeypatch.setenv(key, value)


def test_exports_sanitized_completed_demo_deals_and_hash_manifest(tmp_path, monkeypatch):
    configure(monkeypatch)
    stamp = 1800000000000
    api = FakeMT5([deal(0, stamp, -0.35), deal(1, stamp + 1000, -0.35)])
    result = collector.collect_evidence(
        api, tmp_path, days=30,
        now=lambda: datetime.fromtimestamp((stamp + 2000) / 1000, tz=timezone.utc),
    )
    assert api.shutdown_called
    assert result["status"] == "OBSERVATIONS_CAPTURED"
    summary = json.loads((tmp_path / "round_trip_cost_summary.json").read_text())
    assert summary["complete_round_trip_position_count"] == 1
    observed = summary["round_trip_observations"][0]
    assert observed["observed_commission_usd_per_lot_per_side_equivalent"] == 3.5
    assert summary["commission_schedule_status"].startswith("UNVERIFIED")
    assert summary["net_performance_allowed"] is False
    csv_text = (tmp_path / "demo_deals_sanitized.csv").read_text()
    assert "987654321" not in csv_text and "123456789" not in csv_text
    assert "must-not-export" not in csv_text
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["files"]["demo_deals_sanitized.csv"]["sha256"]
    assert json.loads((tmp_path / "broker_account_snapshot.json").read_text())["login_persisted"] is False


def test_no_deal_history_is_a_nonfatal_evidence_gap(tmp_path, monkeypatch):
    configure(monkeypatch)
    api = FakeMT5([])
    result = collector.collect_evidence(api, tmp_path)
    assert result["status"] == "NEEDS_DEMO_DEAL_HISTORY"
    summary = json.loads((tmp_path / "round_trip_cost_summary.json").read_text())
    assert summary["deal_count_xauusd"] == 0
    assert summary["net_performance_allowed"] is False


def test_incomplete_position_is_not_used_for_round_turn_cost(tmp_path, monkeypatch):
    configure(monkeypatch)
    api = FakeMT5([deal(1, 1800000000000, -0.70)])
    collector.collect_evidence(api, tmp_path)
    summary = json.loads((tmp_path / "round_trip_cost_summary.json").read_text())
    observation = summary["round_trip_observations"][0]
    assert observation["round_trip_complete_in_export"] is False
    assert observation["observed_commission_usd_per_lot_per_side_equivalent"] is None


def test_collector_source_has_no_order_or_position_management_calls():
    source = SOURCE.read_text()
    for forbidden in (
        "order_send(", "order_check(", "order_send_async(",
        "positions_get(", "orders_get(",
    ):
        assert forbidden not in source


def test_invalid_history_window_fails_before_terminal_initialization(tmp_path):
    api = FakeMT5([])
    with pytest.raises(collector.DiagnosticFailure, match="between 1 and 3650"):
        collector.collect_evidence(api, tmp_path, days=0)
    assert not api.shutdown_called
