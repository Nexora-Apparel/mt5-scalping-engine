from pathlib import Path
from types import SimpleNamespace
import re

import pytest

from tools.mt5_python_readonly_diagnostic import (
    DEMO_TRADE_MODE,
    DiagnosticConfig,
    DiagnosticFailure,
    run_diagnostic,
    validate_account,
    validate_quote,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mt5_python_readonly_diagnostic.py"
WORKFLOW = ROOT / ".github" / "workflows" / "veltrix-demo-python-diagnostics.yml"


class FakeClock:
    def __init__(self):
        self.monotonic = 100.0
        self.epoch_ms = 1_800_000_000_000

    def now_ms(self):
        return self.epoch_ms

    def sleep(self, seconds):
        self.monotonic += seconds
        self.epoch_ms += int(seconds * 1000)


class FakeMT5:
    def __init__(self, clock, *, trade_mode=DEMO_TRADE_MODE, connected=True):
        self.clock = clock
        self.trade_mode = trade_mode
        self.connected = connected
        self.shutdown_called = False
        self.initialize_args = None

    def initialize(self, *args, **kwargs):
        self.initialize_args = (args, kwargs)
        return True

    def terminal_info(self):
        return SimpleNamespace(connected=self.connected)

    def account_info(self):
        return SimpleNamespace(
            login=12345678,
            server="Exness-MT5Trial",
            trade_mode=self.trade_mode,
            company="Exness",
        )

    def symbol_select(self, symbol, enabled):
        return symbol in ("XAUUSD", "XAGUSD") and enabled

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01, digits=2)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(
            bid=3000.00,
            ask=3000.20,
            time_msc=self.clock.now_ms(),
        )

    def last_error(self):
        return (1, "fake error")

    def shutdown(self):
        self.shutdown_called = True


def test_account_identity_accepts_only_exact_demo_login_and_server():
    clock = FakeClock()
    api = FakeMT5(clock)
    result = validate_account(api, 12345678, "Exness-MT5Trial")
    assert result["connected"] is True
    assert result["login_match"] is True
    assert result["server_match"] is True
    assert result["trade_mode"] == DEMO_TRADE_MODE


@pytest.mark.parametrize(
    ("trade_mode", "connected", "message"),
    [
        (2, True, "not DEMO"),
        (0, False, "not connected"),
    ],
)
def test_account_guard_fails_closed(trade_mode, connected, message):
    api = FakeMT5(FakeClock(), trade_mode=trade_mode, connected=connected)
    with pytest.raises(DiagnosticFailure, match=message):
        validate_account(api, 12345678, "Exness-MT5Trial")


def test_quote_guard_checks_freshness_and_spread():
    clock = FakeClock()
    api = FakeMT5(clock)
    quote = validate_quote(api, "XAUUSD", clock.now_ms(), 15_000, 1_000)
    assert quote["symbol"] == "XAUUSD"
    assert quote["age_ms"] == 0
    assert quote["spread_points"] == pytest.approx(20.0)

    with pytest.raises(DiagnosticFailure, match="stale"):
        validate_quote(api, "XAUUSD", clock.now_ms() + 30_000, 15_000, 1_000)


def test_full_diagnostic_passes_only_after_five_stable_samples_and_shuts_down():
    clock = FakeClock()
    api = FakeMT5(clock)
    events = []
    config = DiagnosticConfig(
        terminal_path=r"C:\\MT5\\terminal64.exe",
        login=12345678,
        password="not-a-real-secret",
        server="Exness-MT5Trial",
        stable_samples_required=5,
        timeout_seconds=30,
        sample_interval_seconds=1,
    )

    run_diagnostic(
        api,
        config,
        emit_fn=lambda event, **fields: events.append((event, fields)),
        now_ms_fn=clock.now_ms,
        monotonic_fn=lambda: clock.monotonic,
        sleep_fn=clock.sleep,
    )

    assert api.initialize_args[1]["login"] == 12345678
    assert api.initialize_args[1]["server"] == "Exness-MT5Trial"
    assert api.initialize_args[1]["portable"] is True
    assert api.shutdown_called is True
    assert sum(event == "QUOTE_SAMPLE" for event, _ in events) == 5
    assert events[-1][0] == "DIAGNOSTIC_PASSED"


def test_workflow_is_read_only_and_installs_pinned_official_python_package():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "MetaTrader5==5.0.6231" in workflow
    assert "AllowLiveTrading=0" in workflow
    assert "Enabled=0" in workflow
    assert "MT5_LOGIN" in workflow and "MT5_PASSWORD" in workflow and "MT5_SERVER" in workflow
    forbidden = (r"\bmt5\.order_send\s*\(", r"\bmt5\.order_check\s*\(", r"\bmt5\.order_send_async\s*\(")
    for pattern in forbidden:
        assert not re.search(pattern, script), pattern
