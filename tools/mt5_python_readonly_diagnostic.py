"""Read-only MT5 DEMO account and XAUUSD broker-contract quote diagnostic.

Discovers the XAUUSD broker suffix from the connected account catalogue and
verifies the contract currencies. It never submits or manages orders.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

CANONICAL_SYMBOLS = ("XAUUSD",)
DEMO_TRADE_MODE = 0


class DiagnosticFailure(RuntimeError):
    """A fail-closed account, terminal, symbol, or quote validation failure."""


@dataclass(frozen=True)
class DiagnosticConfig:
    terminal_path: str
    login: int
    password: str
    server: str
    max_quote_age_ms: int = 15_000
    max_spread_points: float = 1_000.0
    stable_samples_required: int = 5
    timeout_seconds: int = 90
    sample_interval_seconds: float = 1.0


def emit(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def validate_account(mt5: Any, expected_login: int, expected_server: str) -> dict[str, Any]:
    terminal = mt5.terminal_info()
    if terminal is None:
        raise DiagnosticFailure(f"terminal_info unavailable; last_error={mt5.last_error()}")
    if not bool(getattr(terminal, "connected", False)):
        raise DiagnosticFailure("terminal is not connected to a trade server")
    if bool(getattr(terminal, "trade_allowed", True)):
        raise DiagnosticFailure("terminal trading permission is enabled; read-only guard requires it disabled")
    if bool(getattr(terminal, "dlls_allowed", True)):
        raise DiagnosticFailure("terminal DLL imports are enabled; read-only guard requires it disabled")
    account = mt5.account_info()
    if account is None:
        raise DiagnosticFailure(f"account_info unavailable; last_error={mt5.last_error()}")
    login_match = int(account.login) == expected_login
    server_match = str(account.server) == expected_server
    trade_mode = int(account.trade_mode)
    if not login_match:
        raise DiagnosticFailure("connected account login does not match configured login")
    if trade_mode != DEMO_TRADE_MODE:
        raise DiagnosticFailure(f"account trade mode is not DEMO (observed={trade_mode})")
    if not server_match:
        raise DiagnosticFailure("connected account server does not match configured server")
    return {
        "connected": True, "terminal_trade_allowed": False, "terminal_dlls_allowed": False,
        "login_match": login_match, "server_match": server_match, "trade_mode": trade_mode,
        "company": str(getattr(account, "company", "")),
    }


def _symbol_name(item: Any) -> str:
    return str(getattr(item, "name", item if isinstance(item, str) else ""))


def discover_symbol(mt5: Any, canonical: str) -> str:
    """Resolve only XAUUSD with an optional unambiguous broker suffix."""
    if canonical != "XAUUSD":
        raise DiagnosticFailure("instrument scope violation: XAUUSD is the only supported instrument")
    catalogue = mt5.symbols_get()
    if catalogue is None:
        raise DiagnosticFailure(f"symbol catalogue unavailable; last_error={mt5.last_error()}")
    candidates = []
    for item in catalogue:
        name = _symbol_name(item)
        normalized = re.sub(r"[^A-Z0-9]", "", name.upper())
        if not normalized.startswith(canonical):
            continue
        base = str(getattr(item, "currency_base", "") or "").upper()
        profit = str(getattr(item, "currency_profit", "") or "").upper()
        if base and base != "XAU":
            continue
        if profit and profit != "USD":
            continue
        candidates.append(name)
    candidates = sorted(set(candidates), key=lambda name: (name.upper() != canonical, len(name), name))
    if canonical in candidates:
        candidates = [canonical]
    if len(candidates) != 1:
        hints = [_symbol_name(item) for item in catalogue
                 if "XAU" in _symbol_name(item).upper()]
        raise DiagnosticFailure(
            f"XAUUSD: expected one canonical broker symbol, found {len(candidates)}; "
            f"candidates={candidates}; gold_catalogue_hints={sorted(set(hints))[:30]}"
        )
    resolved = candidates[0]
    if not mt5.symbol_select(resolved, True):
        raise DiagnosticFailure(f"XAUUSD: broker symbol {resolved} exists but could not be selected")
    return resolved


def validate_quote(mt5: Any, symbol: str, now_ms: int, max_quote_age_ms: int,
                   max_spread_points: float, canonical: str | None = None) -> dict[str, Any]:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise DiagnosticFailure(f"{symbol}: symbol_info unavailable; last_error={mt5.last_error()}")
    point = float(getattr(info, "point", 0.0))
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise DiagnosticFailure(f"{symbol}: no readable tick; last_error={mt5.last_error()}")
    bid, ask, tick_time_ms = float(tick.bid), float(tick.ask), int(tick.time_msc)
    if not all(math.isfinite(v) for v in (point, bid, ask)) or point <= 0 or bid <= 0 or ask <= bid or tick_time_ms <= 0:
        raise DiagnosticFailure(f"{symbol}: invalid point, bid, ask, or tick timestamp")
    age_ms = now_ms - tick_time_ms
    if age_ms < -5_000 or age_ms > max_quote_age_ms:
        raise DiagnosticFailure(f"{symbol}: quote stale or timestamp invalid (age_ms={age_ms})")
    spread_points = (ask - bid) / point
    if not math.isfinite(spread_points) or spread_points <= 0 or spread_points > max_spread_points:
        raise DiagnosticFailure(f"{symbol}: spread outside configured limit (spread_points={spread_points:.2f})")
    return {"canonical": canonical or "XAUUSD", "broker_symbol": symbol, "bid": bid, "ask": ask,
            "spread_points": round(spread_points, 2), "age_ms": age_ms,
            "time_msc": tick_time_ms, "digits": int(getattr(info, "digits", 0))}


def run_diagnostic(mt5: Any, config: DiagnosticConfig, *, emit_fn: Callable[..., None] = emit,
                   now_ms_fn: Callable[[], int] | None = None,
                   monotonic_fn: Callable[[], float] = time.monotonic,
                   sleep_fn: Callable[[float], None] = time.sleep) -> None:
    if config.login <= 0 or not config.password or not config.server:
        raise DiagnosticFailure("required account configuration is missing")
    if not config.terminal_path:
        raise DiagnosticFailure("terminal executable path is missing")
    if not 1_000 <= config.max_quote_age_ms <= 60_000:
        raise DiagnosticFailure("quote-age limit is outside safe bounds")
    if not 0 < config.max_spread_points <= 10_000:
        raise DiagnosticFailure("spread limit is outside safe bounds")
    if not 2 <= config.stable_samples_required <= 30:
        raise DiagnosticFailure("stable sample count is outside safe bounds")
    if not 15 <= config.timeout_seconds <= 300:
        raise DiagnosticFailure("diagnostic timeout is outside safe bounds")
    clock_ms = now_ms_fn or (lambda: int(time.time() * 1000))
    emit_fn("INITIALIZING", portable=True, timeout_ms=120_000)
    if not mt5.initialize(config.terminal_path, login=config.login, password=config.password,
                          server=config.server, timeout=120_000, portable=True):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")
    try:
        identity = validate_account(mt5, config.login, config.server)
        emit_fn("ACCOUNT_VERIFIED", **identity)
        resolved = {"XAUUSD": discover_symbol(mt5, "XAUUSD")}
        emit_fn("SYMBOLS_RESOLVED", symbols=resolved)
        started = monotonic_fn()
        stable_samples = 0
        while monotonic_fn() - started < config.timeout_seconds:
            validate_account(mt5, config.login, config.server)
            try:
                quotes = [validate_quote(mt5, resolved["XAUUSD"], clock_ms(),
                                         config.max_quote_age_ms, config.max_spread_points, "XAUUSD")]
            except DiagnosticFailure as exc:
                stable_samples = 0
                emit_fn("QUOTE_BLOCKED", reason=str(exc), stable_samples=stable_samples)
            else:
                stable_samples += 1
                emit_fn("QUOTE_SAMPLE", sample=stable_samples, quotes=quotes)
            if stable_samples >= config.stable_samples_required:
                emit_fn("DIAGNOSTIC_PASSED", account_mode="DEMO", login_match=True,
                        server_match=True, symbols=resolved, stable_samples=stable_samples,
                        trading="disabled")
                return
            sleep_fn(config.sample_interval_seconds)
        raise DiagnosticFailure("XAUUSD did not produce enough consecutive fresh, valid quotes before timeout")
    finally:
        mt5.shutdown()


def main() -> int:
    try:
        config = DiagnosticConfig(
            terminal_path=os.environ.get("MT5_TERMINAL", r"C:\MT5\terminal64.exe"),
            login=int(os.environ.get("MT5_LOGIN", "")),
            password=os.environ.get("MT5_PASSWORD", ""),
            server=os.environ.get("MT5_SERVER", ""),
        )
        import MetaTrader5 as mt5
        run_diagnostic(mt5, config)
        return 0
    except (ValueError, DiagnosticFailure) as exc:
        emit("DIAGNOSTIC_FAILED", reason=str(exc))
        return 1
    except Exception as exc:
        emit("DIAGNOSTIC_ERROR", error_type=type(exc).__name__, reason=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
