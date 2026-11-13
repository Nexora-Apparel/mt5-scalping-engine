# XAUUSD market-regime research

## Purpose

`tools/mt5_xauusd_market_regimes.py` adds descriptive, adaptive regime tags to the verified XAUUSD tick-feature windows. It is offline research only. It does not produce entry/exit signals, labels for supervised training, orders, or profitability claims.

## Causal classification

For each window, the classifier compares current realized volatility, trend efficiency, and tick-count rate with quantiles calculated from preceding completed windows only. Defaults are a 60-window trailing lookback and 30 prior observations required before classification. The current window is appended to the history only after its label is assigned.

The output includes the exact prior-history count, prior-history time bounds, and p25/p75 thresholds used for each classification. Each session is classified independently; thresholds are not pooled across sessions or promoted to universal market constants.

## Regime dimensions

- Volatility: LOW / NORMAL / HIGH, relative to prior-session p25/p75.
- Trend structure: RANGE / MIXED / TREND, using trend-efficiency quantiles.
- Direction: UP / DOWN / FLAT, from the current window's observed mid-price return.
- Activity: QUIET / NORMAL / ACTIVE, using prior tick-count-rate quantiles.

The composite label combines volatility, trend structure, and direction. Activity remains a separate dimension so it cannot be mistaken for a directional signal.

## Warm-up and missing data

The first windows remain WARMUP until the minimum prior history exists. If a current window lacks movement or activity measurements (for example, a one-tick window), it remains UNCLASSIFIED_CURRENT_DATA. No missing value is imputed and no future window is consulted.

## Run

```bash
python -m tools.mt5_xauusd_market_regimes \
  --input feature-windows.json \
  --lookback-windows 60 \
  --min-history 30 \
  --output market-regimes.json
```

## Safety and research controls

- Input must be a PASS, research-only, XAUUSD feature dataset with a valid SHA-256 source reference.
- Feature windows must be UTC-epoch-aligned and strictly chronological; their tick counts must sum exactly to the declared source record count.
- No lookahead: current and future observations never enter the current threshold calculation.
- Tick-count rate is not traded volume. No order, fill, spread-cost, or execution quality is inferred.
- Regime tags are not trade permission and must not be connected to production scheduling or Telegram.
