# XAUUSD strategy hypothesis registry

## Status

The hypotheses in `research/xauusd_strategy_hypotheses.json` are **pre-registered and untested**. They are research questions, not trading signals or recommendations. No candidate is considered validated.

## Candidate families

1. **Trend continuation (H1):** unusually high trend efficiency combined with a large directional displacement; test continuation over 5, 10, 15, 30, and 60 seconds.
2. **Range reversion (H2):** large displacement with low trend efficiency; test partial reversion over the same horizons.
3. **Activity-confirmed expansion (H3):** elevated tick-count rate and realized volatility together; test whether activity adds information beyond price displacement.

## Causal controls

- All trigger thresholds are rolling empirical quantiles from the preceding 60 populated feature windows, with at least 30 valid prior observations.
- The current window is excluded from its own thresholds. Future windows are never used for trigger features.
- History resets at each session boundary.
- The definitions and evaluation rules must be frozen before chronological holdout evaluation.
- Future outcomes are measured from observed bid/ask ticks. No forward fill is permitted.
- Entry and exit sides must reflect actual bid/ask quotes. Commission, slippage, and target-quote tolerance must be separately documented and frozen.

## Evaluation requirements

For each horizon, record event count, coverage, side-adjusted gross and net returns, spread cost, commission, slippage assumption, adverse/favourable excursion, stop-touch ordering, and uncertainty intervals. Compare candidates against matched baseline windows and each other. Report results by session and time block; do not pool away regime or feed differences.

No thresholds are to be optimized against the final chronological holdout. A candidate remains unvalidated until it survives the later walk-forward and prospective DEMO gates.

## Scope and safety

XAUUSD only. Exness DEMO research data only. No orders, live trading, production deployment, scheduling, or Telegram activation are permitted by this registry.
