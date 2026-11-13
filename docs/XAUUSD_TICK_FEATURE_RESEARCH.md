# XAUUSD tick feature research

## Purpose

`tools/mt5_xauusd_feature_research.py` converts a previously collected, provenance-verified XAUUSD DEMO tick CSV into fixed-width descriptive feature windows. It is an offline research component. It does not connect to MT5, place orders, produce trading signals, infer labels, or claim profitability.

## Inputs and validation

The feature builder calls the existing market profiler first. The CSV must therefore match its manifest SHA-256 and record count, have a PASS manifest, DEMO provenance, trading and DLL imports disabled, valid UTC timestamps, valid quotes, and XAUUSD-only scope. The instrument point size is read from the verified manifest for spread normalization.

## Feature definitions

Windows are aligned to UTC epoch boundaries. The default width is five seconds; supported widths are 1–300 seconds. No missing ticks are forward-filled and no data is borrowed from later windows.

Each populated window contains:

- Tick count and observed tick span / tick-count rate (not traded volume).
- Mid-price OHLC, computed from bid/ask midpoint.
- Mid-price log return and high-low range in basis points.
- Realized volatility: square root of the sum of squared consecutive within-window mid-price log returns, expressed in basis points.
- Trend efficiency: absolute net mid-price movement divided by the sum of absolute consecutive movements; zero for a flat path.
- Median, p95, and maximum quoted spread in broker points.
- Maximum inter-tick gap and count of gaps exceeding one second.
- Quote-change ratio, based on consecutive midpoint changes.

A window with one tick has no measurable within-window tick rate and receives null. Boundary windows can be partial. These are intentional properties, not filled or extrapolated observations.

## Run locally

```bash
python -m tools.mt5_xauusd_feature_research \
  --csv path/to/veltrix_exness_demo_ticks.csv \
  --manifest path/to/manifest.json \
  --window-seconds 5 \
  --output feature-windows.json
```

## Research controls

- Keep source CSV and manifest immutable; the output records the source SHA-256.
- Do not interpret tick-count rate as exchange volume.
- Do not use these descriptive windows as strategy labels or as evidence of executable fills.
- Regime classification, feature selection, and strategy testing are separate future stages and must use chronological, leakage-controlled evaluation.
- This component remains XAUUSD-only and read-only. Trading stays disabled.
