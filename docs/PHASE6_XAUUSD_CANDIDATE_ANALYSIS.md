# Phase 6 — XAUUSD candidate analysis engine

## Purpose

Implement the three frozen Phase 4 formulas as an offline, deterministic event generator. It first revalidates the source CSV and DEMO manifest with the verified feature builder, then reads only completed five-second feature windows and produces candidate research events. It does not calculate PnL, rank candidates, place orders, or authorize execution.

## Candidate calculations

- **Momentum:** compare the current completed close with the close at the registered lookback; standardize the log return by the root-sum-square realized volatility from strictly preceding windows.
- **Mean reversion:** compare the current completed close with the arithmetic mean of the preceding lookback windows; standardize the log displacement by the same past-only volatility scale and reverse direction.
- **Volatility breakout:** form prior high/low from preceding windows; require the prior range to be at or below the registered percentile of 60 past-only rolling range observations; confirm a completed close beyond the boundary by the registered volatility fraction.

The exact equations and finite parameter grids are frozen in `research/xauusd_strategy_registry_v1.json`. Missing history, missing volatility, zero volatility, incomplete compression history, or a gap in the required five-second window sequence suppresses the event. The final observed CSV bucket is excluded because a closed dataset cannot prove that its five-second interval completed; a later bucket must exist before the preceding window can trigger. The engine never treats a later observed window as though it were an immediately preceding five-second window. Future-window mutations must not alter earlier events.

## Output contract

Each event records candidate ID, family, signal window index/end time, direction, holding horizon, parameter values, standardized strength, and the explicit origin `CANDIDATE_RESEARCH_SIGNAL_NOT_TRADE`. Outputs carry the source and registry hashes and are always marked not eligible as final holdout data.

## CLI

```bash
python -m tools.mt5_xauusd_candidate_signals --csv ticks.csv --manifest manifest.json --registry research/xauusd_strategy_registry_v1.json --output candidate-events.json
```

No outcome returns, PnL, net performance, position sizing, or order data is generated. The previously inspected Sessions 8 and 9 may only be used for development smoke checks; their candidate event counts are not strategy evidence.

## MQL5 research integration

`MQL5/Include/Veltrix/CandidateAnalysis.mqh` implements the same three frozen candidate formulas and exact parameter grids. `CandidateWindowBuilder.mqh` aggregates fresh XAUUSD broker quotes into UTC-aligned, completed five-second windows, computes midpoint OHLC and realized volatility, retains bounded history, and preserves gaps rather than synthesizing missing windows. `VeltrixScalper.mq5` connects the builder to the candidate analyzer through `OnTick`; candidate analysis is opt-in (`EnableCandidateAnalysis=false` by default) and emits journal records only. It does not call order APIs.

The adapter uses the existing verified XAUUSD market contract and broker-time quote-freshness check. It finalizes a window only when the first quote in a later window arrives, then evaluates only the last completed window. One-tick windows remain invalid, and discontinuous history suppresses affected candidates. The default EA remains in its existing read-only state unless the user explicitly enables candidate analysis in the EA inputs. The terminal adapter uses MT5-delivered `OnTick` events and is best-effort; event coalescing can omit intermediate ticks, so its output is not a complete tick-history dataset and must never be used as historical replay or execution evidence. Compile and static safety tests verify the integration; live terminal runtime behavior remains a separate operational check and is not required for offline research smoke validation.


## Final Phase 6 CI evidence

Final implementation PR [#47](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/47) passed:
- Project Tests: **172 passed**.
- MQL5 compile: all four configured targets reported **0 errors, 0 warnings**.
- Certified-session candidate smoke: both original CSV/manifest pairs passed provenance validation and candidate generation.

Smoke evidence artifact: [phase6-xauusd-candidate-smoke-43382556581](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43382556581/artifacts/14017027406).

| Development session | Source ticks | Feature windows | Completed windows used | Research candidate events |
|---|---:|---:|---:|---:|
| Session 8 | 5,192 | 360 | 359 | 5,692 |
| Session 9 | 7,646 | 361 | 360 | 4,960 |

All generated records were marked research-only and final-holdout-ineligible. The last observed partial/unproven bucket was excluded. Event totals are generated hypothesis events across parameter combinations and holding horizons, not unique trades, outcomes, or performance evidence.

These two sessions remain development-only. The Phase 6 implementation and compile checks do not establish a predictive edge, profitability, fill quality, or execution readiness. The terminal adapter is opt-in and its live runtime behavior has not been operationally validated.
