# Phase 3 — certified XAUUSD cross-session feature diagnostics

**Gate result: PASS (descriptive research only).**

The offline feature builder and cross-session diagnostics were run against two certified Exness DEMO XAUUSD collection artifacts. Each CSV was checked against its source manifest and SHA-256. The diagnostic required unique source hashes, matching five-second schema, aligned chronological UTC windows, non-overlapping sessions, and exact reconciliation of window tick counts to source records.

## Source provenance

| Field | Session 1 | Session 2 |
|---|---:|---:|
| Collection run | [43333365050](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43333365050) | [43338046880](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43338046880) |
| Artifact | `veltrix-exness-demo-ticks-8` (#13997174371) | `veltrix-exness-demo-ticks-9` (#13999059160) |
| Account / broker symbol | Exness DEMO / XAUUSDm | Exness DEMO / XAUUSDm |
| Source ticks | 5,192 | 7,646 |
| SHA-256 | `a81a9ec96602e3a0f20dad64d50cacd36432715c31f6ecf7e5a5f1b94cb6b2e7` | `d31d8b8f463f0bf74b7f98893fe2b2cd3f078153621ef7f52863e95e963967c1` |
| Five-second windows | 360 | 361 |
| UTC interval | 00:00:10–00:30:10 | 00:34:50–01:04:55 |

The intervals are non-overlapping. Across both sessions, 12,838 source ticks reconcile exactly to 721 feature windows. Both manifests record trading disabled and DLL imports disabled.

## Cross-session distribution comparison

| Metric | Session 1 median | Session 2 median | Relative change |
|---|---:|---:|---:|
| Ticks per 5-second window | 12 | 15 | +25.00% |
| Tick rate (ticks/sec) | 2.9800 | 3.4454 | +15.62% |
| Mid-price range (bps) | 1.1722 | 1.2993 | +10.85% |
| Realized volatility (bps) | 0.9905 | 1.0261 | +3.60% |
| Trend efficiency | 0.2393 | 0.1964 | −17.92% |
| Median spread (broker points) | 240 | 240 | 0% |
| 95th percentile spread (broker points) | 240 | 240 | 0% |
| Median per-window maximum inter-tick gap (ms) | 1,188.5 | 1,136.0 | −4.42% |
| Median gaps over 1 second per window | 2 | 1 | −50.00% |

The median spread was 240 broker points in both sessions; Session 2 reached 260 points at maximum. The verified point size is 0.001, so 240 points equals 0.240 in XAUUSD price units. This is a material cost constraint for short-horizon scalping and must be included in all candidate research. It is not a profitability conclusion.

The median per-window return was near zero. Relative percentage drift is suppressed when the baseline is near zero to avoid misleading percentages.

## Coverage and descriptive relationships

- Session 1: movement-derived fields were populated in all 360 windows.
- Session 2: one of 361 windows contained a single tick; movement-derived fields and tick rate were null for that window, with no imputation.
- Range / realized-volatility Pearson correlation: 0.7505 in Session 1; 0.8507 in Session 2.
- Tick-rate / realized-volatility correlation: 0.6609; 0.8416.
- Trend-efficiency / realized-volatility correlation: −0.3501; −0.4503.
- Median spread was constant within both sessions; correlations involving it are undefined and reported as null.

These are contemporaneous descriptive associations from two short sessions, not causal effects or evidence of predictive power.

## Gate decision

**Phase 3 is complete.** The required two-session comparison is reproducible from the retained certified artifacts using the merged offline tools. Provenance, session separation, null coverage, distributions, correlations, and median drift are recorded above.

This does not establish strategy profitability, market-wide stability, slippage, fill probability, or execution quality. Tick counts are not traded volume. No signals or orders were generated. All collection and research remain read-only. Production deployment, scheduling, and Telegram remain disabled.

## Reproduction

```bash
python -m tools.mt5_xauusd_feature_research --csv session.csv --manifest manifest.json --window-seconds 5 --output session-features.json
python -m tools.mt5_xauusd_feature_diagnostics --inputs session-1-features.json session-2-features.json --output phase3-diagnostics.json
```
