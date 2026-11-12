import csv
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "mt5_demo_tick_collector.py"
spec = importlib.util.spec_from_file_location("mt5_demo_tick_collector", MODULE_PATH)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class Clock:
    def __init__(self):
        self.mono = 100.0
        self.epoch_ms = 1_800_000_000_000

    def monotonic(self):
        return self.mono

    def now(self):
        return datetime.fromtimestamp(self.epoch_ms / 1000, tz=timezone.utc)

    def sleep(self, seconds):
        self.mono += seconds
        self.epoch_ms += int(seconds * 1000)

    def now_ms(self):
        return self.epoch_ms


class FakeMT5:
    COPY_TICKS_ALL = 3

    def __init__(self, clock):
        self.clock = clock
        self.shutdown_called = False

    def initialize(self, *args, **kwargs):
        return True

    def terminal_info(self):
        return SimpleNamespace(connected=True, trade_allowed=False, dlls_allowed=False)

    def account_info(self):
        return SimpleNamespace(login=12345678, server="Exness-MT5Trial",
                               trade_mode=0, company="Exness")

    def symbols_get(self):
        return [
            SimpleNamespace(name="XAUUSDm", currency_base="XAU", currency_profit="USD"),
            SimpleNamespace(name="XAGUSDm", currency_base="XAG", currency_profit="USD"),
        ]

    def symbol_select(self, symbol, enabled):
        return enabled and symbol in ("XAUUSDm", "XAGUSDm")

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01, digits=2)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=3000.0, ask=3000.2, time_msc=self.clock.now_ms())

    def copy_ticks_from(self, symbol, date_from, count, flags):
        return [SimpleNamespace(
            time_msc=self.clock.now_ms(), bid=3000.0, ask=3000.2,
            last=3000.1, volume=1, volume_real=1.0, flags=flags,
        )]

    def last_error(self):
        return (1, "fake error")

    def shutdown(self):
        self.shutdown_called = True


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=collector.HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def valid_row(symbol="XAUUSD", stamp=1_800_000_000_000):
    return {
        "schema_version": "1", "source_id": "exness-demo-test",
        "canonical_symbol": symbol, "broker_symbol": symbol + "m",
        "time_msc": stamp, "time_utc": collector.utc_iso(stamp),
        "bid": "3000.0", "ask": "3000.2", "last": "3000.1",
        "volume": "1.0", "volume_real": "1.0", "flags": 3,
    }


def test_tick_audit_validates_both_symbols_and_hashes_dataset(tmp_path):
    path = tmp_path / "ticks.csv"
    write_rows(path, [valid_row("XAUUSD"), valid_row("XAGUSD")])
    result = collector.audit_ticks(path)
    assert result["status"] == "PASS"
    assert result["records"] == 2
    assert len(result["sha256"]) == 64
    assert set(result["streams"]) == {"XAUUSD", "XAGUSD"}
    assert "max_intertick_gap_ms" in result["streams"]["XAUUSD"]


def test_tick_audit_rejects_duplicate_tick(tmp_path):
    path = tmp_path / "duplicate.csv"
    row = valid_row()
    write_rows(path, [row, row])
    with pytest.raises(collector.DiagnosticFailure, match="duplicate tick"):
        collector.audit_ticks(path)


def test_tick_audit_rejects_timestamp_order_regression(tmp_path):
    path = tmp_path / "order.csv"
    write_rows(path, [valid_row(stamp=1_800_000_000_100),
                      valid_row(stamp=1_800_000_000_000)])
    with pytest.raises(collector.DiagnosticFailure, match="moved backwards"):
        collector.audit_ticks(path)


def test_collector_requires_exactly_bounded_30_minute_session():
    with pytest.raises(collector.DiagnosticFailure, match="only the bounded 30-minute"):
        collector.collect(object(), 60, Path("unused"))


def test_full_bounded_collector_rechecks_demo_and_writes_audited_both_symbol_data(
    tmp_path, monkeypatch
):
    clock = Clock()
    api = FakeMT5(clock)
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "fake-secret")
    monkeypatch.setenv("MT5_SERVER", "Exness-MT5Trial")
    monkeypatch.setenv("MT5_TERMINAL", r"C:\MT5\terminal64.exe")

    manifest = collector.collect(
        api, 30, tmp_path,
        monotonic=clock.monotonic, sleep=clock.sleep, now=clock.now,
    )
    assert api.shutdown_called
    assert manifest["status"] == "PASS"
    assert manifest["duration_seconds"] == 1800.0
    assert manifest["account_mode"] == "DEMO"
    assert manifest["trading_enabled"] is False
    assert manifest["dll_imports_enabled"] is False
    assert manifest["quote_validation_cycles"] == 1800
    assert manifest["instrument_specs"]["XAUUSD"]["point"] == 0.01
    assert manifest["spread_points"]["XAUUSD"]["samples"] == 1800
    assert manifest["streams"]["XAUUSD"]["records"] == 1800
    assert manifest["streams"]["XAGUSD"]["records"] == 1800
    assert (tmp_path / "manifest.json").is_file()
    assert (tmp_path / "veltrix_exness_demo_ticks.csv").is_file()


def test_collector_source_contains_no_order_submission_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        r"\bmt5\.order_send\s*\(",
        r"\bmt5\.order_check\s*\(",
        r"\bmt5\.order_send_async\s*\(",
        r"\bmt5\.positions_get\s*\(",
        r"\bmt5\.orders_get\s*\(",
    )
    import re
    for pattern in forbidden:
        assert not re.search(pattern, source), pattern


def test_incremental_tick_cursor_advances_on_short_batches_and_filters_pre_session_ticks():
    class TickAPI:
        COPY_TICKS_ALL = 3
        def copy_ticks_from(self, symbol, date_from, count, flags):
            return [SimpleNamespace(
                time_msc=1_800_000_000_000, bid=3000.0, ask=3000.2,
                last=3000.1, volume=1, volume_real=1.0, flags=flags,
            )]
        def last_error(self):
            return (1, "fake")

    cursor = datetime.fromtimestamp(1_799_999_998, tz=timezone.utc)
    records = {}
    next_cursor = collector._collect_symbol_ticks(
        TickAPI(), "XAUUSD", "XAUUSDm", "exness-demo-test", cursor,
        records, 1_800_000_000_000,
    )
    assert next_cursor > cursor
    assert len(records) == 1
    assert next(iter(records.values()))["time_msc"] == 1_800_000_000_000



def test_tick_audit_reports_long_intertick_gaps_without_silently_filling_them(tmp_path):
    path = tmp_path / "gaps.csv"
    write_rows(path, [valid_row("XAUUSD", stamp=1_800_000_000_000),
                      valid_row("XAUUSD", stamp=1_800_000_007_500),
                      valid_row("XAGUSD", stamp=1_800_000_000_000)])
    result = collector.audit_ticks(path)
    assert result["streams"]["XAUUSD"]["max_intertick_gap_ms"] == 7500
    assert result["streams"]["XAUUSD"]["gaps_over_5_seconds"] == 1


def test_warmup_waits_for_five_consecutive_fresh_quotes_for_both_symbols():
    clock = Clock()

    class StaleThenFresh(FakeMT5):
        def __init__(self, clock):
            super().__init__(clock)
            self.stale_reads = 4

        def symbol_info_tick(self, symbol):
            stamp = self.clock.now_ms()
            if self.stale_reads:
                self.stale_reads -= 1
                stamp -= 30_000
            return SimpleNamespace(bid=3000.0, ask=3000.2, time_msc=stamp)

    api = StaleThenFresh(clock)
    symbols = {"XAUUSD": "XAUUSDm", "XAGUSD": "XAGUSDm"}
    quotes = collector.wait_for_fresh_quotes(
        api, symbols, 12345678, "Exness-MT5Trial",
        timeout_seconds=15, stable_samples_required=5,
        monotonic=clock.monotonic, sleep=clock.sleep, now=clock.now,
    )
    assert len(quotes) == 2
    assert {quote["canonical"] for quote in quotes} == {"XAUUSD", "XAGUSD"}
    assert clock.mono >= 106.0


def test_warmup_fails_closed_when_quotes_never_become_fresh():
    clock = Clock()

    class AlwaysStale(FakeMT5):
        def symbol_info_tick(self, symbol):
            return SimpleNamespace(
                bid=3000.0, ask=3000.2, time_msc=self.clock.now_ms() - 60_000
            )

    api = AlwaysStale(clock)
    symbols = {"XAUUSD": "XAUUSDm", "XAGUSD": "XAGUSDm"}
    with pytest.raises(collector.DiagnosticFailure, match="fresh quote warm-up failed"):
        collector.wait_for_fresh_quotes(
            api, symbols, 12345678, "Exness-MT5Trial",
            timeout_seconds=3, stable_samples_required=2,
            monotonic=clock.monotonic, sleep=clock.sleep, now=clock.now,
        )
