from pathlib import Path
from types import SimpleNamespace
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mt5_python_readonly_diagnostic import (
    CANONICAL_SYMBOLS, DEMO_TRADE_MODE, DiagnosticConfig, DiagnosticFailure,
    run_diagnostic, validate_account, validate_quote, discover_symbol,
)

SCRIPT = ROOT / "tools" / "mt5_python_readonly_diagnostic.py"
WORKFLOW = ROOT / ".github" / "workflows" / "veltrix-demo-python-diagnostics.yml"


class FakeClock:
    def __init__(self):
        self.monotonic = 100.0
        self.epoch_ms = 1_800_000_000_000
    def now_ms(self): return self.epoch_ms
    def sleep(self, seconds):
        self.monotonic += seconds
        self.epoch_ms += int(seconds * 1000)


class FakeMT5:
    def __init__(self, clock, *, trade_mode=DEMO_TRADE_MODE, connected=True, trade_allowed=False):
        self.clock, self.trade_mode, self.connected, self.trade_allowed = clock, trade_mode, connected, trade_allowed
        self.shutdown_called = False
        self.initialize_args = None
    def initialize(self, *args, **kwargs):
        self.initialize_args = (args, kwargs)
        return True
    def terminal_info(self):
        return SimpleNamespace(connected=self.connected, trade_allowed=self.trade_allowed, dlls_allowed=False)
    def account_info(self):
        return SimpleNamespace(login=12345678, server="Exness-MT5Trial", trade_mode=self.trade_mode, company="Exness")
    def symbols_get(self):
        return [
            SimpleNamespace(name="XAUUSDm", currency_base="XAU", currency_profit="USD"),
            SimpleNamespace(name="XAGUSDm", currency_base="XAG", currency_profit="USD"),
        ]
    def symbol_select(self, symbol, enabled): return symbol == "XAUUSDm" and enabled
    def symbol_info(self, symbol): return SimpleNamespace(point=0.01, digits=2)
    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=3000.0, ask=3000.2, time_msc=self.clock.now_ms())
    def last_error(self): return (1, "fake error")
    def shutdown(self): self.shutdown_called = True


def test_instrument_allowlist_is_exactly_xauusd():
    assert CANONICAL_SYMBOLS == ("XAUUSD",)
    api = FakeMT5(FakeClock())
    assert discover_symbol(api, "XAUUSD") == "XAUUSDm"
    with pytest.raises(DiagnosticFailure, match="XAUUSD is the only"):
        discover_symbol(api, "XAGUSD")


def test_account_identity_accepts_only_exact_demo_login_and_server():
    result = validate_account(FakeMT5(FakeClock()), 12345678, "Exness-MT5Trial")
    assert result["connected"] is True
    assert result["terminal_trade_allowed"] is False
    assert result["terminal_dlls_allowed"] is False
    assert result["login_match"] is True and result["server_match"] is True
    assert result["trade_mode"] == DEMO_TRADE_MODE


@pytest.mark.parametrize(("trade_mode", "connected", "trade_allowed", "message"), [
    (2, True, False, "not DEMO"), (0, False, False, "not connected"),
    (0, True, True, "trading permission is enabled"),
])
def test_account_guard_fails_closed(trade_mode, connected, trade_allowed, message):
    api = FakeMT5(FakeClock(), trade_mode=trade_mode, connected=connected, trade_allowed=trade_allowed)
    with pytest.raises(DiagnosticFailure, match=message):
        validate_account(api, 12345678, "Exness-MT5Trial")


def test_quote_guard_checks_freshness_and_spread():
    clock, api = FakeClock(), None
    api = FakeMT5(clock)
    quote = validate_quote(api, "XAUUSDm", clock.now_ms(), 15000, 1000, "XAUUSD")
    assert quote["broker_symbol"] == "XAUUSDm" and quote["canonical"] == "XAUUSD"
    assert quote["age_ms"] == 0 and quote["spread_points"] == pytest.approx(20.0)
    with pytest.raises(DiagnosticFailure, match="stale"):
        validate_quote(api, "XAUUSDm", clock.now_ms() + 30000, 15000, 1000)


def test_full_diagnostic_passes_after_five_gold_samples_and_shuts_down():
    clock, api, events = FakeClock(), None, []
    api = FakeMT5(clock)
    config = DiagnosticConfig(r"C:\\MT5\\terminal64.exe", 12345678, "not-a-real-secret",
                              "Exness-MT5Trial", stable_samples_required=5,
                              timeout_seconds=30, sample_interval_seconds=1)
    run_diagnostic(api, config, emit_fn=lambda event, **fields: events.append((event, fields)),
                   now_ms_fn=clock.now_ms, monotonic_fn=lambda: clock.monotonic, sleep_fn=clock.sleep)
    assert api.initialize_args[1]["login"] == 12345678
    assert api.initialize_args[1]["portable"] is True
    assert api.shutdown_called
    assert sum(event == "QUOTE_SAMPLE" for event, _ in events) == 5
    assert events[-1][0] == "DIAGNOSTIC_PASSED"
    assert events[-1][1]["symbols"] == {"XAUUSD": "XAUUSDm"}


def test_broker_suffix_resolution_rejects_ambiguous_and_wrong_contracts():
    api = FakeMT5(FakeClock())
    api.symbols_get = lambda: [
        SimpleNamespace(name="XAUUSDm", currency_base="XAU", currency_profit="USD"),
        SimpleNamespace(name="XAUUSDpro", currency_base="XAU", currency_profit="USD"),
    ]
    with pytest.raises(DiagnosticFailure, match="found 2"):
        discover_symbol(api, "XAUUSD")
    api.symbols_get = lambda: [SimpleNamespace(name="XAUUSDm", currency_base="XAG", currency_profit="USD")]
    with pytest.raises(DiagnosticFailure, match="found 0"):
        discover_symbol(api, "XAUUSD")


def test_workflow_and_diagnostic_remain_read_only():
    workflow, script = WORKFLOW.read_text(), SCRIPT.read_text()
    assert "windows-latest" in workflow and "MetaTrader5==5.0.6231" in workflow
    assert "AllowLiveTrading=0" in workflow and "Enabled=0" in workflow
    assert all(name in workflow for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"))
    for pattern in (r"\bmt5\.order_send\s*\(", r"\bmt5\.order_check\s*\(", r"\bmt5\.order_send_async\s*\("):
        assert not re.search(pattern, script)
