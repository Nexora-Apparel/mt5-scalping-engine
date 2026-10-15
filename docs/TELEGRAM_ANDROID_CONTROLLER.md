# Android + Telegram controller (read-only scaffold)

## What this stage does
- Runs on the user's Android phone in Pydroid 3.
- Telegram commands: `/whoami`, `/start`, `/stop`, `/status`, `/emergency`, `/balance`.
- Owner restriction for all controls/account queries.
- `/balance` authenticates with Deriv and requests balance only, and rejects accounts unless Deriv explicitly reports a virtual/demo account.
- Credentials are prompted interactively (hidden input for tokens) and are not stored in this source file.
- No order placement or live trading is implemented. `/start` only marks monitoring as armed; the emergency stop defaults ON.

## Before using
1. Revoke the Deriv token previously shared in chat. Do not use it again.
2. Create a replacement token and keep it private. Prefer the minimum permissions needed for read-only validation first.
3. Create a Telegram bot with the official BotFather and keep its bot token private.
4. Install Pydroid 3, then install packages listed in `requirements-android.txt`.
5. Run `scripts/telegram_controller_android.py`. On first run, enter the Telegram bot token, Deriv App ID, replacement Deriv token, and your numeric Telegram user ID. If you do not know your ID, enter `0`, start the process, message the bot `/whoami`, stop the process, and restart with the numeric ID. While ID is 0, owner-restricted commands are unavailable.
6. Send `/balance` in a private chat with the bot. Confirm the response says demo connection OK.

## Android behavior
This process runs on the phone, not on Telegram's servers. Pydroid must remain running and connected to the internet. Android may stop background processes; battery optimization settings can affect reliability. Stopping the process means it cannot receive commands or monitor the market.

## Not yet implemented
- Strategy market-data loop
- Validated Deriv product/symbol and strategy adaptation
- Trade order placement
- SL/TP and risk sizing tested against Deriv's exact contract specifications
- Reconnect/heartbeat handling and durable audit logs

Do not add order placement until the demo connection works and strategy testing and risk controls are reviewed. This scaffold is not a profitable or production-ready trading bot.
