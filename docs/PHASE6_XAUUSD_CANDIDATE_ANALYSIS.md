# Phase 6 — XAUUSD candidate analysis engine

## Purpose

Implement the three frozen Phase 4 formulas as an offline, deterministic event generator. It first revalidates the source CSV and DEMO manifest with the verified feature builder, then reads only completed five-second feature windows and produces candidate research events. It does not calculate PnL, rank candidates, place orders, or authorize execution.

## Candidate calculations

- **Momentum:** compare the current completed close with the close at the registered lookback; standardize the log return by the root-sum-square realized volatility from strictly preceding windows.
- **Mean reversion:** compare the current completed close with the arithmetic mean of the preceding lookback windows; standardize the log displacement by the same past-only volatility scale and reverse direction.
- **Volatility breakout:** form prior high/low from preceding windows; require the prior range to be at or below the registered percentile of 60 past-only rolling range observations; confirm a completed close beyond the boundary by the registered volatility fraction.

The exact equations and finite parameter grids are frozen in `research/xauusd_strategy_registry_v1.json`. Missing history, missing volatility, zero volatility, incomplete compression history, or a gap in the required five-second window sequence suppresses the event. The engine never treats a later observed window as though it were an immediately preceding five-second window. Future-window mutations must not alter earlier events.

## Output contract

Each event records candidate ID, family, signal window index/end time, direction, holding horizon, parameter values, standardized strength, and the explicit origin `CANDIDATE_RESEARCH_SIGNAL_NOT_TRADE`. Outputs carry the source and registry hashes and are always marked not eligible as final holdout data.

## CLI

```bash
python -m tools.mt5_xauusd_candidate_signals --csv ticks.csv --manifest manifest.json --registry research/xauusd_strategy_registry_v1.json --output candidate-events.json
```

No outcome returns, PnL, net performance, position sizing, or order data is generated. The previously inspected Sessions 8 and 9 may only be used for development smoke checks; their candidate event counts are not strategy evidence.

## MQL5 research integration

`MQL5/Include/Veltrix/CandidateAnalysis.mqh` provides XAUUSD-only implementations of the same momentum, mean-reversion, and volatility-breakout formulas for completed five-second feature windows. It rejects incomplete or discontinuous histories and emits only in-memory research-candidate records. `VeltrixScalper.mq5` includes the module; the MQL5 compile workflow verifies the integration.

The current live-quote collector produces rolling snapshots rather than the fixed completed-window stream required by this module. The candidate module is therefore not invoked on live quotes yet. A fixed-window adapter and runtime verification must be completed before live terminal analysis is enabled. This does not affect the offline Python candidate generator.
