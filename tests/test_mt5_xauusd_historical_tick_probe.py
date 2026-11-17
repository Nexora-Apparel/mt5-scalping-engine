import csv
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import mt5_xauusd_historical_tick_probe as probe_module


def ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def tick(stamp: int, *, bid=3000.0, ask=3000.2, last=3000.1,
         volume=1.0, volume_real=1.0, flags=3):
    return SimpleNamespace(
        time_msc=stamp, bid=bid, ask=ask, last=last,
        volume=volume, volume_real=volume_real, flags=flags,
    )


class FakeHistoricalMT5:
    COPY_TICKS_ALL = 3

    def __init__(self, batches=None):
        self.batches = batches or []
        self.calls = []
        self.shutdown_called = False
        self.initialize_args = None

    def initialize(self, *args, **kwargs):
        self.initialize_args = (args, kwargs)
        return True

    def symbol_select(self, symbol, enabled):
        return symbol == "XAUUSDm" and enabled

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01) if symbol == "XAUUSDm" else None

    def copy_ticks_range(self, symbol, start, end, flags):
        assert symbol == "XAUUSDm" and flags == self.COPY_TICKS_ALL
        self.calls.append((start, end))
        if len(self.calls) > len(self.batches):
            return []
        return self.batches[len(self.calls) - 1]

    def last_error(self):
        return (1, "fake historical error")

    def shutdown(self):
        self.shutdown_called = True


@pytest.fixture
def demo_guards(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "test-only-placeholder")
    monkeypatch.setenv("MT5_SERVER", "Exness-MT5Trial")
    monkeypatch.delenv("MT5_TERMINAL", raising=False)
    monkeypatch.setattr(
        probe_module, "connect_expected_account",
        lambda *args, **kwargs: {"trade_mode": probe_module.DEMO_TRADE_MODE},
    )
    monkeypatch.setattr(probe_module, "validate_account", lambda *args, **kwargs: {})
    monkeypatch.setattr(probe_module, "discover_symbol", lambda *args, **kwargs: "XAUUSDm")


def test_parse_utc_requires_timezone_and_normalizes_offsets():
    assert probe_module.parse_utc("2026-11-13T12:00:00Z").tzinfo == timezone.utc
    assert probe_module.parse_utc("2026-11-13T13:00:00+01:00") == probe_module.parse_utc(
        "2026-11-13T12:00:00Z"
    )
    with pytest.raises(ValueError, match="include Z"):
        probe_module.parse_utc("2026-11-13T12:00:00")


def test_probe_retrieves_non_overlapping_chunks_and_writes_verified_csv(
    tmp_path, demo_guards
):
    start = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 13, 9, 2, tzinfo=timezone.utc)
    stamps = [
        ms(start),
        ms(start + timedelta(seconds=59, milliseconds=999)),
        ms(start + timedelta(minutes=1)),
        ms(end),
    ]
    api = FakeHistoricalMT5([
        [tick(stamps[0]), tick(stamps[1])],
        [tick(stamps[2]), tick(stamps[2])],  # provider duplicate is removed
        [tick(stamps[3])],                  # inclusive final endpoint is retained
    ])

    result = probe_module.probe(api, start, end, tmp_path)

    assert api.shutdown_called
    assert api.initialize_args[0][0] == r"C:\MT5\terminal64.exe"
    assert result["status"] == "PASS"
    assert result["account_mode"] == "DEMO"
    assert result["trading_enabled"] is False
    assert result["order_submission"] is False
    assert result["position_management"] is False
    assert result["chunks_requested"] == 3
    assert len(api.calls) == 3
    assert api.calls[0][0] < start
    assert api.calls[0][1] > start + timedelta(minutes=1) - timedelta(milliseconds=1)
    assert api.calls[1][0] < start + timedelta(minutes=1)
    assert api.calls[1][1] > start + timedelta(minutes=2) - timedelta(milliseconds=1)
    assert api.calls[2][0] < end
    assert api.calls[2][1] > end

    csv_path = tmp_path / result["csv_file"]
    raw = csv_path.read_bytes()
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert b"\\n" not in raw
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert [int(row["time_msc"]) for row in rows] == sorted(stamps)
    assert all(row["canonical_symbol"] == "XAUUSD" for row in rows)
    manifest_text = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert manifest_text.endswith("\n")
    assert result["first_tick_utc"] == probe_module.utc_iso(stamps[0])
    assert result["last_tick_utc"] == probe_module.utc_iso(stamps[-1])


@pytest.mark.parametrize(
    "bad_tick, message",
    [
        (tick(1), "outside the requested UTC interval"),
        (tick(1794560400000, bid=float("nan")), "non-finite"),
        (tick(1794560400000, bid=3001.0, ask=3000.0), "invalid bid/ask"),
    ],
)
def test_probe_rejects_invalid_or_out_of_range_ticks(
    tmp_path, demo_guards, bad_tick, message
):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    end = start + timedelta(seconds=30)
    api = FakeHistoricalMT5([[bad_tick]])

    with pytest.raises(probe_module.DiagnosticFailure, match=message) as exc_info:
        probe_module.probe(api, start, end, tmp_path)

    if "outside the requested UTC interval" in message:
        diagnostic = str(exc_info.value)
        assert "tick=" in diagnostic
        assert "delta_from_start_ms=" in diagnostic
        assert "delta_from_end_ms=" in diagnostic
        assert "requested=" in diagnostic

    assert api.shutdown_called
    assert not (tmp_path / "xauusd_historical_ticks.csv").exists()
    assert not (tmp_path / "xauusd_historical_ticks.csv.partial").exists()


def test_probe_rejects_non_monotonic_provider_order(tmp_path, demo_guards):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    first = ms(start + timedelta(seconds=2))
    second = ms(start + timedelta(seconds=1))
    api = FakeHistoricalMT5([[tick(first), tick(second)]])

    with pytest.raises(probe_module.DiagnosticFailure, match="moved backwards within a chunk"):
        probe_module.probe(api, start, start + timedelta(seconds=3), tmp_path)

    assert api.shutdown_called
    assert not (tmp_path / "xauusd_historical_ticks.csv").exists()


def test_probe_fails_closed_when_account_is_not_demo(tmp_path, demo_guards, monkeypatch):
    monkeypatch.setattr(
        probe_module, "connect_expected_account",
        lambda *args, **kwargs: {"trade_mode": 1},
    )
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    api = FakeHistoricalMT5()

    with pytest.raises(probe_module.DiagnosticFailure, match="verified DEMO"):
        probe_module.probe(api, start, start + timedelta(seconds=1), tmp_path)

    assert api.shutdown_called
    assert not api.calls


def test_probe_rejects_empty_interval_and_non_millisecond_boundaries(tmp_path, demo_guards):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    api = FakeHistoricalMT5()

    with pytest.raises(probe_module.DiagnosticFailure, match="increasing UTC interval"):
        probe_module.probe(api, start, start, tmp_path)
    assert not api.shutdown_called

    with pytest.raises(probe_module.DiagnosticFailure, match="whole milliseconds"):
        probe_module.probe(api, start + timedelta(microseconds=1), start + timedelta(seconds=1), tmp_path)
    assert not api.shutdown_called


def test_probe_rejects_empty_historical_result_without_stale_success_files(
    tmp_path, demo_guards
):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    api = FakeHistoricalMT5([[]])

    with pytest.raises(probe_module.DiagnosticFailure, match="no historical ticks"):
        probe_module.probe(api, start, start + timedelta(seconds=1), tmp_path)

    assert api.shutdown_called
    assert not (tmp_path / "xauusd_historical_ticks.csv").exists()
    assert not (tmp_path / "xauusd_historical_ticks.csv.partial").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_probe_stops_on_broker_api_error_and_shuts_down(tmp_path, demo_guards):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)

    class FailedAPI(FakeHistoricalMT5):
        def copy_ticks_range(self, *args):
            self.calls.append(args)
            return None

    api = FailedAPI()
    with pytest.raises(probe_module.DiagnosticFailure, match="historical tick request failed"):
        probe_module.probe(api, start, start + timedelta(seconds=1), tmp_path)

    assert api.shutdown_called
    assert not (tmp_path / "xauusd_historical_ticks.csv").exists()



def test_probe_filters_mt5_boundary_spill_but_keeps_exact_requested_window(
    tmp_path, demo_guards
):
    start = datetime(2026, 11, 17, 13, 50, 0, 282000, tzinfo=timezone.utc)
    end = start + timedelta(seconds=30)
    before = ms(start) - 145
    inside = ms(start)
    after = ms(end) + 120
    api = FakeHistoricalMT5([[
        tick(before), tick(inside), tick(after)
    ]])

    result = probe_module.probe(api, start, end, tmp_path)

    with (tmp_path / result["csv_file"]).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["time_msc"]) for row in rows] == [inside]
    assert result["records"] == 1
    assert result["chunks"][0]["discarded_guard_band_records"] == 2
    assert result["mt5_query_boundary_padding_milliseconds"] == 2000



def test_probe_discards_mt5_spill_outside_padded_query_boundary(
    tmp_path, demo_guards
):
    start = datetime(2026, 11, 17, 13, 50, 0, 282000, tzinfo=timezone.utc)
    end = start + timedelta(seconds=30)
    # MT5 returned a tick 242 ms before the padded query's start in the
    # production failure. It is within the bounded response-spill tolerance
    # but must never enter the accepted logical interval.
    beyond_query_start = ms(start) - probe_module.RANGE_PADDING_MILLISECONDS - 242
    inside = ms(start) + 10
    api = FakeHistoricalMT5([[
        tick(beyond_query_start), tick(inside)
    ]])

    result = probe_module.probe(api, start, end, tmp_path)

    with (tmp_path / result["csv_file"]).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["time_msc"]) for row in rows] == [inside]
    assert result["chunks"][0]["discarded_guard_band_records"] == 1
    assert result["mt5_query_response_spill_tolerance_milliseconds"] == 2000


def test_probe_rejects_ticks_beyond_mt5_guard_band(tmp_path, demo_guards):
    start = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    far_outside = (
        ms(start)
        - probe_module.RANGE_PADDING_MILLISECONDS
        - probe_module.RANGE_RESPONSE_SPILL_TOLERANCE_MILLISECONDS
        - 1
    )
    api = FakeHistoricalMT5([[tick(far_outside)]])

    with pytest.raises(probe_module.DiagnosticFailure, match="outside the requested UTC interval"):
        probe_module.probe(api, start, start + timedelta(seconds=30), tmp_path)

    assert api.shutdown_called
    assert not (tmp_path / "xauusd_historical_ticks.csv").exists()
