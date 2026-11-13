# Phase 6 — XAUUSD candidate signal implementation

## Current implementation slice

`tools/mt5_xauusd_candidate_signals.py` converts a verified five-second feature JSON into deterministic candidate events using the frozen `research/xauusd_strategy_registry_v1.json`. It does not evaluate outcomes or submit orders.

### Implemented candidate families

- Momentum continuation: current completed-window close versus the close exactly one registered lookback earlier; standardized by the root-sum-square of realized-volatility values from strictly preceding windows.
- Mean reversion: current close versus the arithmetic mean of strictly preceding completed-window closes; standardized by the same past-only volatility scale.
- Volatility breakout: prior-window high/low, prior-only volatility scale, and a compression percentile computed from 60 past rolling-range observations. Current-window data is excluded from the prior range and compression history.

All preregistered parameter combinations and 5/15/30/60-second outcome horizons are represented. Signals require complete contiguous five-second history. Missing fields, gaps, non-finite values, invalid timestamps, wrong schema, wrong instrument, or invalid registry fail closed or suppress the affected candidate event. Event IDs are deterministic and include candidate, direction, horizon, parameters, source hash, and signal-window end.

## Causal and safety controls

- Only completed five-second feature windows are consumed.
- Rolling calculations use strictly preceding windows; the current window is used only for its own signal observation.
- No forward fill, centered rolling calculation, or future-window access.
- XAUUSD only; the preregistered Exness DEMO data contract is enforced through the registry.
- Output is explicitly research-only and carries `execution_sent=false`.
- The two inspected certified development sessions remain ineligible for validation or final holdout.
- Commission remains unverified. This engine does not calculate net returns or approve candidates.
- No MQL5 order API is part of this Python module.

## CLI

```bash
python -m tools.mt5_xauusd_candidate_signals \
  --features session-features.json \
  --registry research/xauusd_strategy_registry_v1.json \
  --output candidate-events.json
```

## Phase 6 completion gate

This Python implementation is only one component of Phase 6. Phase 6 is not complete until:
1. Unit tests pass, including deterministic output, lookahead-invariance, gap handling, invalid-input rejection, and all candidate families.
2. MQL5 research integration implements the same frozen candidate definitions and is compile-verified.
3. Python/MQL5 parity fixtures produce matching candidate decisions and no execution path is introduced.
4. Research workflows remain read-only and the existing collector is unchanged.

No strategy is approved by implementation or compilation. Phase 7 risk controls, Phase 8 walk-forward evaluation, Phase 9 prospective DEMO validation, and Phase 10 release remain locked.
