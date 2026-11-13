# VELTRIX XAUUSD multi-position scalping policy v1

## Purpose and boundary

This is a new operating-policy layer for future strategy research. It does not modify the frozen Phase 8 walk-forward registry or its one-position-per-candidate evaluation rule. It does not authorize broker execution. The EA, collection workflows, and research evaluator remain read-only.

## Strategy operating rules

- Instrument: broker-verified XAUUSD only.
- Style: scalping only.
- Position age: each position must be closed no earlier than 10 seconds and no later than 60 seconds after confirmed opening, unless its protective stop or take-profit is hit sooner.
- Each position must have its own valid protective stop-loss and take-profit before any future execution authorization.
- No daily minimum trade count, no daily maximum trade count, no profit target, and no profit ceiling.
- No fixed simultaneous-position count ceiling. The position registry is per-position and may track multiple simultaneous positions.
- Position count is not a risk budget. New positions are permitted only while aggregate open risk, margin reserve, broker volume rules, and all independent safety checks pass.

## Automatic position sizing

For each proposed position:

1. Validate the current account equity and exact broker contract metadata.
2. Determine the stop distance from a strategy-provided, validated price level.
3. Calculate loss per lot from broker tick size and loss-side tick value.
4. Calculate the per-trade risk budget from equity and the configured risk percentage.
5. Calculate remaining aggregate portfolio risk capacity after accounting for every open or unresolved position.
6. Use the smaller of per-trade budget and remaining portfolio capacity.
7. Round volume down to the broker volume step; never round up to minimum volume.
8. Reject the intent if the result is below broker minimum, exceeds broker maximum, breaches margin reserve, or any required input is missing or stale.

Aggregate exposure must include positions in OPEN, CLOSE_DUE, CLOSE_PENDING, UNKNOWN, or PROTECTION_FAILURE state. A position is removed from exposure only after broker-history evidence confirms closure and the close is reconciled. Unknown broker outcomes must never be treated as flat.

## Independent safety constraints

- Existing per-trade risk hard ceiling remains 0.25% of equity.
- Existing aggregate open-risk hard ceiling remains 0.50% of equity.
- Broker free-margin reserve and broker volume limits remain mandatory.
- The account must be a verified Exness DEMO hedging account for any future multi-position execution design.
- Stale quotes, excessive spread, invalid contract metadata, missing tick economics, invalid stops, or failed margin estimates block new entries.
- Every position has an independent 10-60 second deadline and TP/SL lifecycle.
- Emergency stop remains independent of strategy signals.

## Daily loss shutdown: unresolved safety deviation

The owner requested a daily shutdown threshold in the 50-60% account-loss range. The existing risk engine has a stricter hard ceiling of 1.00% daily equity loss and Phase 7 persistence tests are built around that policy. A 50-60% daily loss allowance would permit catastrophic account impairment and is not adopted by this change. The 1.00% hard ceiling remains active until a separate risk-policy review establishes a defensible alternative. Manual reactivation must not bypass the daily lock or emergency stop without an audited reset procedure.

## Phase 8 isolation

The frozen Phase 8 evaluation plan explicitly requires one open position per candidate configuration. That rule remains unchanged for its preregistered walk-forward evidence. The multi-position policy is a separate research track and must receive its own simulator, cost model, overlap accounting, portfolio-level statistics, and prospective validation before any comparison or execution use.

## Current implementation state

- The MQL5 risk allocator no longer rejects an intent solely because a position-count ceiling has been reached.
- The risk-control configuration no longer requires exactly one simultaneous position.
- Aggregate open risk and broker margin remain the binding portfolio constraints.
- The position registry already maintains independent per-position lifecycle and 10-60 second close deadlines.
- No order submission, modification, or closure APIs are added.
- No live or DEMO execution is enabled.
