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

- Daily loss ceiling: 15.00% of server-day starting equity; overall account loss ceiling: 50.00% of original owner-verified deposit. Neither is a profit target.
- Existing per-trade risk hard ceiling remains 0.25% of equity.
- Existing aggregate open-risk hard ceiling remains 0.50% of equity.
- Broker free-margin reserve and broker volume limits remain mandatory.
- The account must be a verified Exness DEMO hedging account for any future multi-position execution design.
- Stale quotes, excessive spread, invalid contract metadata, missing tick economics, invalid stops, or failed margin estimates block new entries.
- Every position has an independent 10-60 second deadline and TP/SL lifecycle.
- Emergency stop remains independent of strategy signals.

## Daily and overall account loss shutdown

The owner selected two independent loss ceilings:

- Daily drawdown: 15.00% of verified server-day starting equity. This is a hard shutdown threshold, not a loss target.
- Overall account drawdown: 50.00% of the owner-verified original deposit. This baseline never resets.

There is no daily profit target or profit cap. The strategy may continue seeking valid opportunities while all risk checks pass. Floating PnL and verified trading costs must count toward both loss limits. When either ceiling is reached, new entries stop and existing positions enter the independent protective-exit/emergency handling path.

Both locks require explicit owner-controlled manual reactivation. A daily rearm must append a durable audit event and establish a fresh verified daily baseline; it must not clear the overall account lock or emergency stop. The MQL5 risk journal supports a durable DAILY_REARM event that removes the active daily lock—even when it originated on a prior server day—and stores the verified equity used as the new daily baseline. `CVxRiskControls.RearmDailyLossLock` is now exposed only through `MQL5/Scripts/DailyLossOwnerRearm.mq5`, a manually launched DEMO/USD-only script requiring exact login/server, owner-reviewed original-deposit evidence, operator ID, reason, traceable evidence reference, and an exact confirmation phrase. The daily rearm event stores operator, reason, evidence reference, timestamp and new equity baseline in the existing checksum-chained journal. It cannot clear the overall-loss lock or emergency stop. Operator attribution is self-asserted, not cryptographic identity. After success, the owner must reinitialize/restart the EA to reload the daily baseline. MQL5 run `43546992691` passed; its inspected artifact confirms the daily-rearm operator/reason/evidence metadata append and restart replay. The manual daily script compiled with the exact confirmation-phrase check. The script has not been run against a real Exness DEMO account. The `OverallAccountLossGuard.mqh` is wired into `CVxRiskControls`: initialization requires an owner-reviewed original deposit; live evaluation requires the exact Exness DEMO identity and USD account currency; both volume calculation and intent registration evaluate current equity against the 50% ceiling; and lock state contributes to `IsLocked`. Overall-loss reactivation is now routed through `MQL5/Scripts/OverallLossOwnerRearm.mq5`, a manually launched DEMO-only script. It requires the exact login/server, USD currency, an explicit original-deposit evidence attestation, operator ID, reason, traceable evidence reference, and exact confirmation phrase. Successful reactivation requires equity strictly above the 50% boundary and preserves the immutable baseline. Lock, reactivation intent, commit, and abort records are written to a checksum-chained account-scoped audit file. An incomplete intent is reconciled as locked on restart. Operator ID is self-asserted and is not cryptographic identity; the terminal must remain owner-controlled. Because the script runs as a separate MT5 process context, the owner must reinitialize/restart the EA after successful script completion so its in-memory lock state reloads from the audited persistent state. Latest MQL5 compile/runtime validation for the audit-chain implementation, including the traceable evidence-reference input, passed in run `43546992691`; all six terminal result sentinels passed. The owner script compiled successfully but has not been run against a real Exness DEMO account.

## Phase 8 isolation

The frozen Phase 8 evaluation plan explicitly requires one open position per candidate configuration. That rule remains unchanged for its preregistered walk-forward evidence. The multi-position policy is a separate research track and must receive its own simulator, cost model, overlap accounting, portfolio-level statistics, and prospective validation before any comparison or execution use.

## Current implementation state

- The MQL5 risk allocator no longer rejects an intent solely because a position-count ceiling has been reached.
- `PortfolioExposureLedger.mqh` aggregates per-position stop risk and margin across a dynamic list with no count ceiling. `RiskControls.mqh` now has an overload that reads aggregate open risk and active count directly from this ledger before invoking dynamic lot sizing; close-pending, unknown, and protection-failure records continue reserving exposure until broker close confirmation. It rejects duplicate position identifiers/tickets, permits broker-refreshed margin estimates, never permits stop-risk widening, and removes confirmed closed exposure from the active ledger. The position registry automatically compacts its runtime list after a broker-confirmed close (and exposes bulk compaction), while the durable risk journal remains the audit history; unlimited trade counts therefore do not imply unbounded in-memory closed-position records.
- The risk-control configuration no longer requires exactly one simultaneous position.
- Aggregate open risk and broker margin remain the binding portfolio constraints.
- The position registry already maintains independent per-position lifecycle and 10-60 second close deadlines.
- `OverallAccountLossGuard.mqh` is integrated into `CVxRiskControls` intent approval and uses account equity (therefore floating P/L and costs already reflected by the broker in equity); it does not infer the original deposit from current balance. Any additional verified costs not yet reflected in account equity still require explicit accounting. Overall-loss reactivation uses the local manual owner script and checksum-chained audit; operator attribution remains self-asserted rather than cryptographic.
- The offline multi-position simulator now requires an explicitly owner-verified original-deposit baseline, enforces the independent 50.00% overall-loss boundary, recalculates per-trade and aggregate risk budgets from marked equity at each entry, and adjusts available margin for realized/floating gross PnL. Synthetic robustness tests cover this guard, dynamic sizing, overlapping aggregate exposure, and 0/1/2/5-point slippage sensitivity. They validate mechanics, not profitability; commission remains unverified and net scoring is disabled.
- No order submission, modification, or closure APIs are added.
- No live or DEMO execution is enabled.


## Overall-loss guard verification suite (2026-11-14)
- Added a dedicated MQL5 runtime script, `OverallAccountLossGuardRuntimeTest.mq5`, using synthetic equity injection compiled only under `VELTRIX_RISK_TEST`. The production build does not expose that test API.
- The first dedicated runtime artifact passed unverified-baseline rejection, initial immutable baseline, 50% boundary activation, persisted lock replay, conflicting baseline rejection, rearm rejection at/below the threshold, successful manual rearm above the threshold, baseline retention, second threshold breach, global-variable checksum tampering and partial-state rejection. The audit-chain implementation adds operator attribution, evidence reference, exact confirmation phrase, intent/commit/abort events, restart reconciliation, and a separate manual DEMO reactivation script. These changes passed the latest dedicated terminal runtime run `43546992691`.
- The guard runtime script and both manual owner-reactivation scripts are wired into the Windows MetaTrader compile workflow; Python regression assertions cover operator/reason/evidence attribution, manual confirmation, USD-only DEMO identity, and absence of order APIs.
- The terminal runtime artifact `Veltrix-risk-runtime-results` from run `43546992691` was downloaded and inspected. All six sentinels passed; the overall-loss sentinel confirms audited reactivation, invalid confirmation rejection, audit tamper rejection and partial-state rejection. The owner script revision includes the required traceable evidence-reference input.
- The synthetic test validates guard persistence and decision logic. The manual script is a deliberate local owner action with self-asserted operator attribution, not cryptographic identity verification. Do not expose it remotely or treat its input phrase as a secret.


## Development data suitability gate

The only pinned tick datasets currently available for this separate track are development Sessions 8 and 9 from 13 November 2026. They are not validation or holdout data and must not be relabelled.

| Development session | Tick records | Duration | Maximum inter-tick gap | Spread |
|---|---:|---:|---:|---:|
| Session 8 | 5,192 | 30 minutes | 3.040 s | 240 points on every observed quote |
| Session 9 | 7,646 | 30 minutes | 3.812 s | median 240 points; 7 observations at 260 points |

Both manifests identify Exness DEMO XAUUSDm, USD profit currency, 100 oz contract size, 0.001 point and tick size, and disabled trading/DLL permissions. Both datasets have zero non-zero tick-volume observations. The two sessions are on the same UTC date and are development-only.

The 240-point spread corresponds to 0.240 in XAUUSD price units on the manifest's 0.001 point scale. This is a material cost hurdle for a 10–60 second strategy. The manifests also do not provide verified loss/profit tick values, margin-per-lot, stop-level metadata, or owner-verified original-deposit input. Therefore these datasets can support feature/candidate smoke tests only; they cannot support a broker-economics portfolio replay, net scoring, validation certification, or profitability conclusions. Fresh distinct-date sessions and a provenance-verified broker specification plus commission evidence are required before that stage.


## Daily-loss owner reactivation

`MQL5/Scripts/DailyLossOwnerRearm.mq5` provides a separate manual control for the 15.00% daily lock. It requires the exact Exness DEMO login/server, USD account currency, owner attestation that the immutable original-deposit evidence was reviewed, operator ID, a specific reason, a traceable evidence reference, and the exact phrase `VELTRIX OWNER CONFIRM DAILY REACTIVATION`. The journal records the metadata and verified equity baseline in a single checksum-chained `DAILY_REARM` event. Operator, reason, and evidence fields reject empty, whitespace-only, delimiter-injected, or overlength values. This script cannot clear the overall-loss lock or emergency stop. The owner must restart/reinitialize the EA after successful reactivation. The script is compiled by CI but must never be remotely exposed; operator ID remains self-asserted attribution, not cryptographic authentication.
