# Phase 7 — XAUUSD DEMO risk engine and safety controls

## Status

Implementation is in progress on `feature/phase7-demo-risk-controls`. The module is deliberately a local risk-policy layer and does not submit, modify, or close orders. Phase 7 is not complete until final Python tests, MQL5 compilation, and safety review pass.

## Components

- `RiskAllocator.mqh`: finite-input validation, loss-side tick economics, portfolio capacity, broker volume-step rounding down, and skip-below-minimum behavior.
- `RiskControls.mqh`: exact DEMO login/server verification; broker-metadata-confirmed XAUUSD contract restriction; hard risk ceilings; daily equity-loss lock; verified-close loss streak and cooldown; one-position limit; duplicate request-ID rejection; latched emergency stop.
- `ExecutionGuard.mqh`: independent DEMO preflight requiring exact configured login/server, verified XAUUSD base/profit currencies, fresh quote, spread limit, broker-valid volume, mandatory protective stop, stop-distance compliance, margin estimate, and free-margin reserve. It returns a decision only.
- `PositionRegistry.mqh`: per-position lifecycle, hold deadlines, unknown-state handling, and close confirmation only after broker-history evidence.
- `BrokerReconciler.mqh`: read-only position/deal reconciliation; partial exit history, missing history, volume mismatch, or missing protection are not treated as clean closure.
- `ExecutionCoordinator.mqh`: request lifecycle and duplicate-deal accounting; unknown broker outcomes remain blocked until reconciled. It contains no broker submission call.

## Risk policy ceilings

The module rejects configuration above these hard limits:

| Control | Hard ceiling / policy |
|---|---:|
| Risk per trade | 0.25% of current equity |
| Aggregate portfolio open risk | 0.50% of current equity |
| Daily equity loss | 1.00% of server-day starting equity |
| Simultaneous positions | Exactly 1 |
| Post-loss cooldown | 30 seconds minimum; configurable up to 1 hour |
| Consecutive verified losses | Maximum configured value 3 |

These are upper bounds, not claims of safety or profitability. Actual operating values must be set more conservatively where broker economics require it. Position sizing uses `SYMBOL_TRADE_TICK_VALUE_LOSS` and broker tick size; volume is rounded down and the trade is skipped if broker minimum volume would exceed the risk budget.

## Lockout behavior

- Daily loss is measured from the explicit server-day starting-equity baseline to current equity, so floating drawdown is included.
- Once breached, the daily loss lock remains latched until a later verified server-day key is initialized.
- A backward-moving server-day key is rejected. Starting equity cannot be silently replaced during the same day.
- Verified losing closes increment the consecutive-loss count and start a cooldown. A verified profitable close resets the loss streak. A zero-P/L close does not erase it.
- Reaching the configured consecutive-loss limit latches the daily lock.
- Cooldown and emergency stop survive a server-day rollover.
- There is intentionally no emergency-stop reset method. Clearing it requires a separate reviewed operator/session-control procedure.
- Request IDs are retained for deduplication. At 10,000 IDs, the module fails closed rather than discarding history and risking duplicate approval.

## Integration contract

A future DEMO-only caller must, in order:

1. Initialize the risk policy with the exact configured DEMO login and server; never commit account identifiers or credentials into the repository.
2. Verify the connected account is DEMO and matches both configured identity fields.
3. Initialize and maintain a server-day equity baseline; evaluate current equity before every new intent and every sizing decision.
4. Validate the XAUUSD broker contract using base currency XAU and profit currency USD (suffixes are accepted only when metadata confirms the contract).
5. Calculate size with the risk allocator and current aggregate open risk; pass the actual active-position count.
6. Pass the resulting intent through the independent execution preflight, including a mandatory protective stop and reserve margin.
7. Register a unique request ID only after all upstream gates pass; never retry an unknown broker outcome before reconciliation.
8. Update loss streak/cooldown only from a broker-confirmed closing deal and net P/L.

The current VELTRIX EA only includes the module for compilation. No risk-control configuration is activated, no order path is wired, and all collection/diagnostic/research behavior remains read-only.

## Explicit limitations

- The module does not infer the server-day key or starting equity; the caller must obtain both from a verified broker session and preserve the baseline for the day.
- Daily equity loss includes floating P/L but does not replace reconciliation of commissions, swaps, fees, deposits, withdrawals, or broker corrections.
- Consecutive-loss state and request-ID deduplication are in-memory. A future executor must persist and restore these states safely before any demo execution; a terminal restart must not reset a live emergency stop or duplicate protection.
- Position registry/reconciler provide primitives, not a complete durable transaction journal.
- The existing EA is not authorized to execute. Compilation and static tests do not prove runtime broker behavior.
- No live/real-money execution, production deployment, or scheduling is enabled.

## Phase 7 completion gate

- [ ] Python regression tests pass on final commit.
- [ ] MQL5 compile passes with zero errors and zero warnings.
- [ ] Risk policy tests cover invalid numeric inputs, account mismatch, symbol mismatch, stop/margin preflight, daily-loss lock, cooldown, loss streak, duplicate request, and emergency-stop latch.
- [ ] Static scan confirms no order submission/modification/closure APIs in the VELTRIX risk modules or EA.
- [ ] Independent review confirms state persistence and restart behavior are addressed before any future DEMO execution.
- [ ] No production deployment, scheduling, Telegram, or live trading.
