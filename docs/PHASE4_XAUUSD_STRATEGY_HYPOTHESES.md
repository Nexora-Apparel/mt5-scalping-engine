# Phase 4 — preregistered XAUUSD strategy hypotheses

## Objective and boundary

Phase 4 freezes three falsifiable research hypotheses before strategy testing: short-horizon momentum continuation, mean reversion, and volatility breakout. The machine-readable registry is `research/xauusd_strategy_registry_v1.json`; its fail-closed validator is `tools/mt5_xauusd_strategy_registry.py`.

This phase does not produce an approved strategy. No signals are sent to MT5, no orders are placed, and no live or demo execution is enabled.

## Frozen hypotheses

1. **Momentum continuation:** a completed directional impulse, standardized by trailing volatility, predicts continuation over 5, 15, 30, or 60 seconds.
2. **Mean reversion:** a completed displacement from a trailing reference mean predicts reversal over the same horizons.
3. **Volatility breakout:** a confirmed close beyond a preceding compressed range predicts continuation over the same horizons.

Each candidate has a finite parameter grid and explicit direction, invalidation, and fixed-horizon exit definitions. No grid may be expanded after results are observed without a new registry version and a new untouched holdout.

## Quote-crossed outcome convention

- Long entry uses Ask; long exit uses Bid.
- Short entry uses Bid; short exit uses Ask.
- The spread is therefore included once in the gross quote-crossed result. It must not be subtracted a second time.
- Entry is the first valid quote strictly after the completed signal window, within five seconds.
- Exit is the first valid quote at or after the target horizon, no more than two seconds late. Otherwise the outcome is missing, not forward-filled.
- Commission is deliberately marked `UNVERIFIED_REQUIRED_INPUT`. Net candidate evaluation cannot pass until the applicable Exness commission is verified. Slippage values of 0, 1, 2, and 5 points per side are sensitivity assumptions, not measured slippage.

The two already inspected sessions (#8 and #9) are development data only and are explicitly prohibited from use as an untouched final holdout. Later validation and holdout data must be chronological and independent. Purge at least the maximum 60-second outcome horizon plus 60-second signal lookback at partition boundaries.

## Known cost constraint

The measured median spread in both certified sessions was 240 broker points = 0.240 XAUUSD price units at point size 0.001. This is a substantial hurdle relative to a 5–60-second holding horizon. The simulator must report gross quote-crossed results, commission, slippage sensitivity, and net results separately. No gross-only ranking is allowed.

## Validation

Run the registry validator:

```bash
python -m tools.mt5_xauusd_strategy_registry --registry research/xauusd_strategy_registry_v1.json
```

The validator checks XAUUSD-only scope, research-only state, immutable candidate IDs and horizon set, finite positive parameter grids, quote-crossed entry/exit rules, cost requirements, untouched holdout exclusion, and chronological leakage controls.

A passing registry validation proves only that the research plan conforms to its declared contract. It does not prove predictive power, profitability, fill quality, or readiness to trade.
