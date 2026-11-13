# Phase 3 — certified XAUUSD cross-session feature diagnostics

**Result: PASS — descriptive research gate only**

The merged feature builder and cross-session diagnostic logic were run against the two certified Exness DEMO XAUUSD collection artifacts. The source CSVs were rechecked against their manifests and SHA-256 digests before feature generation. The diagnostic accepted only the XAUUSD feature schema, required unique source hashes, chronological UTC windows, non-overlapping sessions, matching five-second widths, and exact reconciliation of per-window tick counts to source records.

## Provenance

| Field | Session 1 | Session 2 |
|---|---:|---:|
| Collection workflow run | [43333365050](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43333365050) | [43338046880](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43338046880) |
| Tick artifact | `veltrix-exness-demo-ticks-8` | `veltrix-exness-demo-ticks-9` |
| Artifact ID | `13997174371` | `13999059160` |
| Canonical / broker symbol | XAUUSD / XAUUSDm | XAUUSD / XAUUSDm |
| Account mode | Exness DEMO | Exness DEMO |
| Source records | 5,192 | 7,646 |
| Source SHA-256 | `a81a9ec96602e3a0f20dad64d50cacd36432715c31f6ecf7e5a5f1b94cb6b2e7` | `d31d8b8f463f0bf74b7f98893fe2b2cd3f078153621ef7f52863e95e963967c1` |
| Five-second feature windows | 360 | 361 |
| Window interval (UTC) | 00:00:10–00:30:10 | 00:34:50–01:04:55 |

Both sessions have distinct hashes and non-overlapping intervals. The source manifests record `trading_enabled=false` and `dll_imports_enabled=false`. Their per-window tick counts reconcile exactly to 12,838 source records across 721 windows.

## Cross-session results

| Metric | Session 1 median | Session 2 median | Session 2 relative change |
|---|---:|---:|---:|
| Tick count / 5-second window | 12 | 15 | +25.00% |
| Tick rate (ticks/sec) | 2.9800 | 3.4454 | +15.62% |
| Mid-price range (bps) | 1.1722 | 1.2993 | +10.85% |
| Realized volatility (bps) | 0.9905 | 1.0261 | +3.60% |
| Trend efficiency | 0.2393 | 0.1964 | −17.92% |
| Median quoted spread (broker points) | 240 | 240 | 0% |
| 95th percentile quoted spread (broker points) | 240 | 240 | 0% |
| Median maximum inter-tick gap (ms) | 1,188.5 | 1,136.0 | −4.42% |
| Median gaps over 1 second / window | 2 | 1 | −50.00% |

Spread observations were predominantly 240 broker points, with 260 points as the maximum observed in Session 2. The verified point size is 0.001, so 240 points corresponds to 0.240 in XAUUSD price units. This is a material transaction-cost constraint for short-horizon scalping and must be modelled explicitly before any strategy candidate can be judged.

The median of the per-window return feature is close to zero in both sessions. Relative percentage drift is deliberately suppressed for near-zero baselines because it is unstable and misleading.

## Data coverage and descriptive relationships

- Session 1: all 360 windows had at least two ticks for movement-derived features.
- Session 2: one of 361 windows contained a single tick; movement-derived fields and tick rate were null for that window, not imputed.
- Contemporaneous Pearson correlation between range and realized volatility was 0.7505 in Session 1 and 0.8507 in Session 2.
- Correlation between tick rate and realized volatility was 0.6609 and 0.8416, respectively.
- Correlation between trend efficiency and realized volatility was −0.3501 and −0.4503, respectively.
- Median quoted spread was constant in both sessions, so correlations involving that constant feature are undefined and correctly reported as null.

These are descriptive associations from two short sessions, not causal relationships or evidence of predictive power.

## Gate decision and limitations

**Phase 3 gate: PASS.** The cross-session report is reproducible from the two named, retained workflow artifacts using the merged offline feature and diagnostic tools. Session identity, hashes, null coverage, distributions, correlations, and median drift are preserved.

This result does not establish profitability, a tradable edge, execution quality, slippage, fill probability, or market-wide stability. Tick counts are not traded volume. No signals or orders were generated. The collector and all research workflows remain read-only; production deployment, scheduling, and Telegram remain disabled.

## Reproduction

Build each feature file with the verified offline feature builder:

```bash
python -m tools.mt5_xauusd_feature_research --csv session.csv --manifest manifest.json --window-seconds 5 --output session-features.json
```

Then compare the two feature files:

```bash
python -m tools.mt5_xauusd_feature_diagnostics --inputs session-1-features.json session-2-features.json --output phase3-diagnostics.json
```
