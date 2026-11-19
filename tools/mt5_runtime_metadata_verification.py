"""Read-only Exness DEMO MT5 runtime and XAUUSD contract metadata verification.

This diagnostic does not request ticks, submit orders, or manage positions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from tools.mt5_demo_tick_collector import (
    DEMO_TRADE_MODE,
    DiagnosticFailure,
    connect_expected_account,
    discover_symbol,
    validate_account,
)


def verify(mt5: Any, terminal: str, login: int, password: str, server: str) -> dict[str, Any]:
    if not mt5.initialize(
        terminal, login=login, password=password, server=server,
        timeout=120_000, portable=True,
    ):
        raise DiagnosticFailure(f"MT5 initialize failed; last_error={mt5.last_error()}")
    try:
        identity = connect_expected_account(mt5, login, password, server)
        if identity.get("trade_mode") != DEMO_TRADE_MODE:
            raise DiagnosticFailure("runtime metadata verification requires a verified DEMO account")
        validate_account(mt5, login, server)

        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            raise DiagnosticFailure("MT5 terminal_info is unavailable")
        dlls_allowed = getattr(terminal_info, "dlls_allowed", None)
        if dlls_allowed is not False:
            raise DiagnosticFailure("effective terminal runtime does not prove DLL imports are disabled")

        broker_symbol = discover_symbol(mt5, "XAUUSD")
        info = mt5.symbol_info(broker_symbol)
        if info is None:
            raise DiagnosticFailure("XAUUSD symbol_info is unavailable")
        base = getattr(info, "currency_base", None)
        profit = getattr(info, "currency_profit", None)
        point = float(getattr(info, "point", 0.0) or 0.0)
        if base != "XAU" or profit != "USD" or not (point > 0 and point < float("inf")):
            raise DiagnosticFailure("XAUUSD contract metadata failed exact XAU/USD and positive-point checks")

        version = mt5.version()
        return {
            "schema": "VELTRIX_MT5_RUNTIME_METADATA_VERIFICATION_V1",
            "status": "PASS",
            "source": "authenticated Exness MT5 DEMO terminal runtime",
            "account_mode": "DEMO",
            "canonical_symbol": "XAUUSD",
            "broker_symbol": broker_symbol,
            "dll_imports_runtime_verified": True,
            "dll_imports_enabled": False,
            "contract_currency_metadata_verified": True,
            "instrument_specs": {
                "XAUUSD": {
                    "broker_symbol": broker_symbol,
                    "currency_base": base,
                    "currency_profit": profit,
                    "point": point,
                }
            },
            "runtime": {
                "dlls_allowed": dlls_allowed,
                "terminal_version": list(version) if isinstance(version, (tuple, list)) else str(version),
                "terminal_build": getattr(terminal_info, "build", None),
                "python_integration_version": getattr(mt5, "__version__", None),
            },
            "trading_enabled": False,
            "order_submission": False,
            "position_management": False,
            "ticks_requested": False,
            "credentials_recorded": False,
        }
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runtime-metadata/verification.json"))
    parser.add_argument("--terminal", default=os.environ.get("MT5_TERMINAL", r"C:\\MT5\\terminal64.exe"))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
        result = verify(
            mt5, args.terminal, int(os.environ["MT5_LOGIN"]),
            os.environ["MT5_PASSWORD"], os.environ["MT5_SERVER"],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (DiagnosticFailure, KeyError, ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
