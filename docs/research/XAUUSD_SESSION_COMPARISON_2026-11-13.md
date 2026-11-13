# XAUUSD certified-session feature comparison — 13 November 2026

## Inputs

| Session | Source CSV SHA-256 | Ticks | Five-second windows | UTC interval (window bounds) |
|---|---|---:|---:|---|
| 8 | `a81a9ec96602e3a0f20dad64d50cacd36432715c31f6ecf7e5a5f1b94cb6b2e7` | 5,192 | 360 | 00:00:10–00:30:10 |
| 9 | `d31d8b8f463f0bf74b7f98893fe2b2cd3f078153621ef7f52863e95e963967c1` | 7,646 | 361 | 00:34:50–01:04:55 |

The two source intervals are non-overlapping. Each source was already certified as an independent Exness DEMO XAUUSD dataset. One single-tick window in Session 9 has null movement-derived metrics; it is not converted into zero movement.

## Per-session medians

| Metric | Session 8 | Session 9 |
|---|---:|---:|
| Ticks per five-second window | 12 | 15 |
| Tick-count rate (ticks/sec; not volume) | 2.9800 | 3.4454 |
| Mid-price range (bps) | 1.1722 | 1.2993 |
| Realized volatility (bps) | 0.9905 | 1.0261 |
| Trend efficiency | 0.2393 | 0.1964 |
| Median quoted spread (broker points) | 240 | 240 |
| p95 quoted spread (broker points) | 240 | 240 |
| Maximum inter-tick gap within a window (ms) | 3,040 | 3,352 |
| Gaps over one second per window | 2 | 1 |

Session 9 had a 25.0% higher median tick count and a 15.6% higher median tick-count rate. Median range was 10.8% higher, while median realized volatility was 3.6% higher and median trend efficiency was 17.9% lower. The median and p95 quoted spread were 240 points in both sessions; Session 9's maximum observed window spread reached 260 points.

## Descriptive correlations

Within each session, realized volatility was positively correlated with tick-count rate (Session 8: 0.6609; Session 9: 0.8416) and mid-price range (0.7505; 0.8507). Trend efficiency was negatively correlated with realized volatility (-0.3501; -0.4503). Spread correlations are undefined because spread was constant in most windows.

## Interpretation limits

These are two short, adjacent-in-time samples, not a representative market study. The differences may reflect market conditions, broker feed behaviour, or session-specific sampling. Correlations are contemporaneous descriptive associations, not causal effects. The results do not establish predictive power, profitability, slippage, fill quality, or execution readiness. No strategy selection was made from this report.
