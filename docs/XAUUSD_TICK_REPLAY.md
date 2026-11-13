# XAUUSD deterministic tick replay

## Purpose

`tools/mt5_xauusd_tick_replay.py` replays a verified DEMO XAUUSD bid/ask CSV against the pre-registered H1/H2/H3 event definitions. It measures observable quote outcomes at 5, 10, 15, 30, and 60 seconds. It does not place orders or simulate broker fills.

## Frozen replay settings

- Feature windows: 5 seconds, generated directly from the verified source CSV.
- Threshold history: preceding 60 populated windows, at least 30 valid prior observations; current window excluded.
- Maximum entry/target quote delay: 1,000 ms. Quotes outside this bound are unavailable; no forward fill.
- Direction and trigger thresholds follow the versioned hypothesis registry.
- Baseline: eligible non-zero-return windows that do not satisfy H1, H2, or H3.
- Commission and slippage are null until verified assumptions are supplied. Net returns therefore remain null.

## Outcome calculations

- Long entry uses ask; long exit uses bid.
- Short entry uses bid; short exit uses ask.
- Reported gross return is bid/ask-adjusted and includes the observed spread.
- Favourable/adverse excursions use the actual chronological quotes between entry and target.
- Invalidation is recorded when a later mid-price crosses the trigger-window opposite extreme. This is an observed quote crossing, not a guaranteed stop fill.
- Entry/target quote delay, availability, event thresholds, and source SHA-256 are retained for audit.

## Run

```bash
python -m tools.mt5_xauusd_tick_replay \
  --csv path/to/veltrix_exness_demo_ticks.csv \
  --manifest path/to/manifest.json \
  --registry research/xauusd_strategy_hypotheses.json \
  --config research/xauusd_replay_config.json \
  --output replay-report.json
```

## Interpretation limits

The replay is a deterministic event study, not a trading backtest or execution simulator. It does not model broker queue position, order rejection, partial fills, market impact, commission, or real slippage. Historical event counts and gross quote returns do not establish profitability or prospective performance. The sample remains too short for strategy validation.
