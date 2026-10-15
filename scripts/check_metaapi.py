"""Read-only MetaApi diagnostic. This script never submits, modifies, or closes trades."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from metaapi_cloud_sdk import MetaApi


def emit(status: str, **details: object) -> None:
    print(json.dumps({"status": status, "checked_at": datetime.now(timezone.utc).isoformat(), **details}, default=str))


async def main() -> int:
    token = os.getenv("METAAPI_TOKEN", "").strip()
    account_id = os.getenv("METAAPI_ACCOUNT_ID", "").strip()
    requested_symbol = os.getenv("SYMBOL", "").strip()

    if not token or not account_id:
        emit(
            "blocked",
            reason="Missing METAAPI_TOKEN or METAAPI_ACCOUNT_ID",
            orders_submitted=False,
        )
        return 2

    api = MetaApi(token)
    connection = None
    try:
        # Fetch the existing account only. Do not create, deploy, or undeploy it.
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()

        account_info = await connection.get_account_information()
        symbols = await connection.get_symbols()

        symbol = requested_symbol
        if not symbol:
            # Only choose a symbol name actually supplied by the broker terminal.
            candidates = ("XAUUSD", "GOLD")
            symbol = next(
                (candidate for candidate in candidates if candidate in symbols),
                "",
            )

        quote = None
        quote_error = None
        if symbol and symbol in symbols:
            try:
                quote = await connection.get_symbol_price(symbol)
            except Exception as exc:  # diagnostic should report quote failure without trading
                quote_error = type(exc).__name__
        elif symbol:
            quote_error = "Configured symbol not present in account symbol list"
        else:
            quote_error = "No XAUUSD/GOLD candidate found; set SYMBOL to an exact broker symbol"

        # Keep output minimal; do not print credentials, account identifiers, balance, or positions.
        connected = bool(getattr(account, "connection_status", None) == "CONNECTED")
        emit(
            "ok" if quote is not None else "partial",
            connection_synchronized=True,
            account_connection_status=getattr(account, "connection_status", "unknown"),
            account_currency=account_info.get("currency") if isinstance(account_info, dict) else None,
            leverage=account_info.get("leverage") if isinstance(account_info, dict) else None,
            symbol=symbol or None,
            symbol_available=bool(symbol and symbol in symbols),
            quote_received=quote is not None,
            quote=quote,
            quote_error=quote_error,
            symbol_count=len(symbols),
            orders_submitted=False,
        )
        return 0 if quote is not None else 1
    except Exception as exc:
        emit(
            "error",
            error_type=type(exc).__name__,
            message=str(exc)[:300],
            orders_submitted=False,
        )
        return 1
    finally:
        if connection is not None:
            try:
                await connection.close()
            except Exception:
                pass
        try:
            await api.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
