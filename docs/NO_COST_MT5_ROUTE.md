# No-cost direct MT5 route (without MetaApi)

## Why this route exists

The MetaApi RPC diagnostic could not synchronize because the MetaApi account is undeployed and the dashboard asks for a balance top-up. This route removes MetaApi from the execution path: an Expert Advisor runs inside the broker's MetaTrader 5 desktop terminal.

## Important platform limitation

The standard MetaTrader 5 desktop terminal and MetaEditor are Windows applications. The MT5 Python package also requires a local desktop terminal and is not a serverless/Linux replacement. This route therefore needs access to a Windows computer with MT5 installed and logged into the Exness **demo** account. The terminal/computer must remain online while the EA runs. An Android-only device cannot host the desktop EA continuously.

## Current scaffold

- `MQL5/Experts/NexoraScalper.mq5` is an experimental direct-terminal EA.
- It uses a closed-bar 9/21 EMA crossover as a provisional test signal, not a validated profitable strategy.
- Order submission is disabled by default (`EnableDemoOrders=false`) and the emergency stop defaults to ON (`EmergencyStop=true`).
- The EA blocks non-demo accounts, enforces a spread ceiling, a single-position-per-symbol rule, a cooldown, risk-based volume sizing, SL/TP, and a persistent start-of-day equity baseline with a daily equity-loss lockout.
- Symbol point sizes and spreads differ by broker and instrument. Inputs must be calibrated for the exact Exness symbol (including suffix) before any demo order test.
- The EA has not yet been compiled in MetaEditor or run in MT5 Strategy Tester. Do not enable order submission or use it on a live account.

## Safe validation sequence

1. Install MT5 desktop from Exness on a Windows computer and log into the demo account.
2. Open MetaEditor, copy the EA into `MQL5/Experts/`, compile it, and resolve any compiler warnings/errors.
3. Run Strategy Tester first with visual mode and historical data; inspect entry timing, spread behavior, SL/TP placement, volume, and drawdown.
4. Keep `EnableDemoOrders=false` and `EmergencyStop=true` until compilation and backtesting have been reviewed.
5. For a controlled demo execution test only, use `EnableDemoOrders=true`, `EmergencyStop=false`, confirm the terminal account is DEMO, and watch every trade. Never test on a live account.

## Cost warning

This avoids MetaApi's deployment balance requirement, but does not guarantee that every part of the setup is free. Exness demo use is typically free; internet and a computer are still required. Do not buy a VPS or fund a live account just to test this scaffold.
