"""Nexora Scalper Telegram controller — Android/Pydroid 3, demo/read-only phase.

This scaffold DOES NOT place trades. /start only arms the controller state.
Trade execution must not be added until demo-account checks, strategy testing,
risk controls, and explicit order-execution safeguards are implemented.
Secrets are requested interactively and kept in process memory only.
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
from typing import Any

import websockets
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

APP_NAME = "Nexora Scalper"
BOT_ACTIVE = False
EMERGENCY_STOP = True
DERIV_APP_ID = ""
DERIV_TOKEN = ""
ALLOWED_USER_ID = 0


def authorized(update: Update) -> bool:
    user = update.effective_user
    return bool(user and ALLOWED_USER_ID and user.id == ALLOWED_USER_ID)


async def deriv_read_only_balance() -> str:
    """Authenticate and read balance only; deliberately contains no trade requests."""
    if not DERIV_APP_ID or not DERIV_TOKEN:
        return "Deriv credentials are not configured in this running session."
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    try:
        async with websockets.connect(uri, open_timeout=12, close_timeout=5) as ws:
            await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
            auth_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
            auth = auth_msg.get("authorize")
            if not auth:
                err = auth_msg.get("error", {}).get("message", "Authorization failed")
                return f"Deriv authorization failed: {err}"
            # Fail closed unless Deriv explicitly identifies this as a virtual/demo account.
            if str(auth.get("is_virtual", "")) not in ("1", "True", "true"):
                return "BLOCKED: Deriv did not confirm this is a virtual/demo account. No trading is enabled."
            await ws.send(json.dumps({"balance": 1, "subscribe": 0}))
            bal_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
            bal = bal_msg.get("balance")
            if not bal:
                err = bal_msg.get("error", {}).get("message", "Balance request failed")
                return f"Connected to demo, but balance retrieval failed: {err}"
            amount = bal.get("balance", "unknown")
            currency = bal.get("currency", "")
            return f"Demo connection OK. Balance: {amount} {currency}".strip()
    except asyncio.TimeoutError:
        return "Deriv API timed out. Check internet and credentials."
    except Exception as exc:
        return f"Deriv connection error: {type(exc).__name__}. Check internet and setup."



async def animate_text(message: Any, frames: list[str], delay: float = 0.35) -> None:
    """Create a lightweight Telegram text animation by editing one message."""
    for frame in frames:
        try:
            await message.edit_text(frame)
        except Exception:
            pass
        await asyncio.sleep(delay)


async def cmd_animate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview the controller's lightweight Telegram animation."""
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    if not update.message:
        return
    message = await update.message.reply_text("◌ Initializing Scalper AI…")
    await animate_text(
        message,
        [
            "◌ Initializing Scalper AI…",
            "◔ Initializing Scalper AI…",
            "◑ Initializing Scalper AI…",
            "◕ Initializing Scalper AI…",
            "● Scalper AI ready",
            "📡 Monitoring: OFF",
            "🛡️ Risk lock: ON",
            "⛔ Trading: DISABLED",
        ],
        delay=0.28,
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if update.message and user:
        await update.message.reply_text(
            f"Your Telegram numeric user ID is: {user.id}\n"
            "Use this ID as the allowed owner ID when starting Nexora Scalper."
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global BOT_ACTIVE, EMERGENCY_STOP
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied. This controller is owner-restricted.")
        return
    if EMERGENCY_STOP:
        if update.message:
            await update.message.reply_text(
                "START BLOCKED: emergency stop is active. This build is read-only and cannot trade."
            )
        return
    BOT_ACTIVE = True
    if update.message:
        await update.message.reply_text(
            "Nexora Scalper is ARMED for monitoring only. Order execution is not implemented."
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global BOT_ACTIVE
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    BOT_ACTIVE = False
    if update.message:
        await update.message.reply_text(
            "Stopped: strategy monitoring is disabled. This controller has no open-order execution."
        )


async def cmd_emergency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global BOT_ACTIVE, EMERGENCY_STOP
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    BOT_ACTIVE = False
    EMERGENCY_STOP = True
    if update.message:
        await update.message.reply_text(
            "EMERGENCY STOP LATCHED. Monitoring is off. No orders can be submitted by this build."
        )


async def cmd_resetstop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the monitoring-only stop latch; this cannot enable order execution."""
    global EMERGENCY_STOP, BOT_ACTIVE
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    EMERGENCY_STOP = False
    BOT_ACTIVE = False
    if update.message:
        await update.message.reply_text(
            "Emergency stop cleared for monitoring controls only. Controller remains STOPPED. "
            "Order execution is not implemented and remains disabled."
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    state = "ARMED (monitoring only)" if BOT_ACTIVE else "STOPPED"
    emergency = "ON" if EMERGENCY_STOP else "OFF"
    if update.message:
        await update.message.reply_text(
            f"{APP_NAME}\nController: {state}\nEmergency stop: {emergency}\n"
            "Execution: DISABLED\nAccount mode: demo-only verification required"
        )


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        if update.message:
            await update.message.reply_text("Access denied.")
        return
    if update.message:
        message = await update.message.reply_text("◌ Connecting to Deriv demo…")
        await animate_text(
            message,
            [
                "◌ Connecting to Deriv demo…",
                "◔ Opening secure connection…",
                "◑ Checking demo authorization…",
                "◕ Requesting balance (read-only)…",
            ],
            delay=0.3,
        )
        result = await deriv_read_only_balance()
        await message.edit_text(
            f"✅ {result}" if result.startswith("Demo connection OK.") else f"⚠️ {result}"
        )


async def post_init(app: Application) -> None:
    # Automatically animate startup in the owner's private Telegram chat when their
    # numeric user ID is configured and they have already opened the bot at least once.
    print(f"{APP_NAME} controller started. Trading execution is disabled.")
    if ALLOWED_USER_ID:
        try:
            message = await app.bot.send_message(
                chat_id=ALLOWED_USER_ID,
                text="◌ Starting Scalper AI…",
            )
            await animate_text(
                message,
                [
                    "◌ Starting Scalper AI…",
                    "◔ Loading controller…",
                    "◑ Checking safety locks…",
                    "◕ Connecting Telegram controls…",
                    "✅ Scalper AI is online",
                    "📡 Monitoring: OFF",
                    "🛡️ Emergency stop: ON" if EMERGENCY_STOP else "🛡️ Emergency stop: OFF",
                    "⛔ Trading: DISABLED",
                ],
                delay=0.32,
            )
        except Exception as exc:
            # Startup must still succeed if the user has not opened the bot yet.
            print(f"Startup animation unavailable: {type(exc).__name__}")


def main() -> None:
    global DERIV_APP_ID, DERIV_TOKEN, ALLOWED_USER_ID
    print(f"=== {APP_NAME}: Telegram controller (read-only/demo phase) ===")
    print("This build does not place orders.")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass(
        "Paste Telegram bot token (input hidden): "
    )
    DERIV_APP_ID = os.environ.get("DERIV_APP_ID") or input("Deriv App ID: ").strip()
    DERIV_TOKEN = os.environ.get("DERIV_API_TOKEN") or getpass.getpass(
        "Paste replacement Deriv demo API token (input hidden): "
    )
    owner_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID") or input(
        "Your Telegram numeric user ID (or 0 to use /whoami first): "
    ).strip()
    try:
        ALLOWED_USER_ID = int(owner_id)
    except ValueError:
        raise SystemExit("Telegram user ID must be a number.")
    if not telegram_token or not DERIV_APP_ID or not DERIV_TOKEN:
        raise SystemExit("Missing required setting. Nothing was started.")
    if ALLOWED_USER_ID < 0:
        raise SystemExit("Telegram user ID must be a positive number or 0.")

    app = Application.builder().token(telegram_token).post_init(post_init).build()
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("animate", cmd_animate))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("emergency", cmd_emergency))
    app.add_handler(CommandHandler("resetstop", cmd_resetstop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    print("Polling Telegram. Keep Pydroid open and Android battery restrictions disabled.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
