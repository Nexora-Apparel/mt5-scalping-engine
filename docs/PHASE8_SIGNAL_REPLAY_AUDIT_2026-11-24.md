# Phase 8 XAUUSD Signal/Replay Reconciliation Audit — 2026-11-24

## Status and preservation

This is a post-run audit of the original Phase 8 historical validation artifact. It does not replace, edit, rerun, or reinterpret the original report. The original artifact and its six source-session CSV/manifest pairs remain immutable. No holdout data was accessed. No candidate was tuned, selected, frozen, or approved. No order execution was enabled.

- Workflow run: 45321781627; job: 138201794479.
- Workflow source commit: 41c9f48a02061e03ab4fd5695b7f83a29ecc9e90.
- Artifact: 14888181358, `veltrix-xauusd-historical-validation-report`.
- Artifact ZIP SHA-256: `e2bd914a1598eb03e1ec83cbe03de2d149609f11c63483a2f934353ab3b2154d`.
- Report status: `RESEARCH_EVALUATION_COMPLETE`; 112 candidate-result rows; `candidate_approval=NOT_APPROVED`; `holdout_eligible=false`; `net_performance_allowed=false`.
- Frozen registry hash in report: `6feaef79f5c1481920b5c2519c72d3ade7aa29849ae9b7cf4fee4e410b024c59`.

## 1. Signal-to-outcome reconciliation

The four validation CSVs were independently re-read and the registered 5-second feature windows, candidate formulas, quote replay, and one-position filtering were independently reconstructed. The independent reconstruction matched **all 112 existing candidate-result rows** for:
- accepted outcome counts in each validation session; and
- zero-slippage gross mean return for every session/configuration/horizon.

This supports the arithmetic and data mapping in the published result rows. It is not an independent broker-fill test; all outcomes remain theoretical quote-crossed marks.

| Validation session | Date | Raw ticks | 5-second feature buckets |
|---|---:|---:|---:|
| validation_01 | 2026-11-16 | 4,680 | 360 |
| validation_02 | 2026-11-17 | 3,815 | 360 |
| validation_03 | 2026-11-18 | 6,912 | 360 |
| validation_04 | 2026-11-19 | 10,852 | 360 |

CSV SHA-256 values:
- validation_01: `a879c204fcdaae667f7a3cb4b92a17023075419a171db9e4bc33e5e5ea772ae6`
- validation_02: `2fedca356aa259cf4fe45d4529616cd2ea6f55c676ea9ffae6ef4555d343badd`
- validation_03: `6a8d8b9d42e855e41eaaa809d2fa681c80426a921efd28fcb0f895770f7fae82`
- validation_04: `02846779b754fae0362e3bff7cd6be01b7d35c5d707a9ea17cdecdc73654626c`

Across the four sessions:
- 3,394 unique signal-trigger instances across parameter configurations were generated; each was expanded into four separate horizon arms, giving 13,576 candidate event records.
- Raw quote replay produced 13,275 `OUTCOME_AVAILABLE` statuses and 301 `EXIT_QUOTE_TIMEOUT` statuses; no `ENTRY_QUOTE_TIMEOUT` occurred.
- After the one-position filter, 5,065 outcomes were accepted, 8,387 events were skipped as overlapping/unresolved, and 124 quote timeouts were actually reached by the sequential filter. These reconcile to 13,576 events.
- The 301 raw exit-timeout statuses include 177 later events that were never attempted because an earlier unresolved exit had already blocked the configuration/horizon lane. Those 177 belong in the skipped count, not the attempted-timeout count.

### Reporting defect: per-session skipped count is low by 177

The report's aggregate `total_skipped` sums to 8,387, but the per-session `skipped_overlapping_or_unresolved` fields sum to 8,210, a shortfall of **177**. In `_summarize_group`, the per-session value is calculated by subtracting every precomputed entry/exit-timeout status from the number of events. That incorrectly subtracts timeout statuses for later events that the sequential filter never attempted after `unresolved=True`. The aggregate loop's `total_skipped` is the correct count; the per-session field is not. This is a reporting/accounting defect and does not change the 5,065 accepted outcomes or their returns.

### Zero-signal configurations are omitted

The preregistered grid contains 30 parameter configurations and four horizons, so a complete report should contain 120 configuration/horizon rows. The report contains 112 because two volatility-breakout parameter configurations emitted no signals:
- 30-second lookback, breakout fraction 1.0, compression percentile 25 or 35;
- 60-second lookback, breakout fraction 1.0, compression percentile 25 or 35.

Those eight zero-event horizon rows are omitted rather than explicitly reported as zero-signal / sample-gate-failed. This is a report-completeness defect, not evidence of a successful candidate.

## 2. Why signal counts are sparse

Signal counts below are unique trigger windows summed across parameter configurations (not multiplied by the four horizon arms):

| Family | validation_01 | validation_02 | validation_03 | validation_04 | Total |
|---|---:|---:|---:|---:|---:|
| Momentum continuation | 884 | 653 | 928 | 596 | 3,061 |
| Mean reversion | 69 | 39 | 83 | 25 | 216 |
| Volatility breakout | 42 | 28 | 28 | 19 | 117 |

The sparse families behave consistently with their registered filters:
- Mean reversion requires a standardized displacement from the preceding-window mean. Raising the threshold from 1.0 to 1.5 or 2.0 sharply reduces triggers. For example, 15-second lookback produced 106 triggers at threshold 1.0, 24 at 1.5, and 6 at 2.0 across all four dates. At 30-second lookback, threshold 2.0 produced one trigger total; at 60 seconds it also produced one.
- Breakout requires both a 60-window past-only compression-percentile qualification and a close beyond the prior range by a fraction of the trailing volatility scale. Only 117 triggers were produced across the four sessions. At 30-second lookback, fraction 0.25 produced 30/36 triggers at compression percentiles 25/35; fraction 0.5 produced 9/12; fraction 1.0 produced one each. At 60-second lookback, fraction 0.5 produced two triggers per compression percentile, and fraction 1.0 produced none.
- The 30-minute sessions contain only 360 five-second buckets. The breakout history requirement delays eligibility until 66 or 72 buckets have elapsed, before the compression and breakout filters are applied. The resulting low sample count is therefore explainable by the registered design and short sample duration; it is not, by itself, proof of a code defect.

## 3. Entry/exit quote timing and spread convention

The current replay implementation uses:
- `bisect_right` for the first quote strictly after the signal-window end;
- a maximum entry delay of 5,000 ms (a quote exactly 5,000 ms late remains eligible);
- `bisect_left` for the first quote at or after entry time plus the registered horizon;
- a maximum exit delay of 2,000 ms;
- long entry at Ask and exit at Bid; short entry at Bid and exit at Ask;
- the spread included once through executable-side crossing; and
- slippage sensitivity of 0, 1, 2, or 5 points per side, with commission left null.

The independent replay found no entry-order, entry-delay, exit-order, or exit-delay violations in the 13,576 events. The 301 raw exit-timeout statuses were caused by no qualifying exit quote within the two-second tolerance. The sequential filter attempted 124 of those before an unresolved exit blocked later events.

## 4. Single-position filter audit

The evaluator applies a separate one-position lane to each candidate ID + parameter set + horizon. This is how the four holding horizons are independently compared. The plan currently says one open position per candidate configuration without explicitly stating that each horizon is a separate simulation lane; that wording should be clarified in a separately versioned plan amendment before any new evaluation.

A latent filter defect exists in the current implementation: it tests `entry_time_msc <= next_free`, where `next_free` is the previous accepted exit time. The decision-time rule should first reject any new signal whose `signal_window_end_msc < next_free`. Otherwise, if a signal occurs while the previous position is open but the first post-signal quote arrives only after the previous exit, the late quote can be accepted even though the signal itself was formed during the open-position interval. No such accepted late-entry case was observed in these four sessions, so this latent defect did not alter the accepted outcomes in this artifact. A synthetic regression test is required.

The filter correctly blocks later signals after an `EXIT_QUOTE_TIMEOUT` because the previous position's exit is unresolved. Entry timeouts do not open a position and do not block later signals.

## 5. Boundary-window contract defect

The feature builder explicitly allows fixed UTC windows to be partial at dataset boundaries. The candidate generator excludes the final observed window but does not exclude the first partial window. In these four sessions, the first tick arrived 30–153 ms after the 17:30:00 UTC boundary. Five distinct momentum signal triggers (20 horizon event records) used that first boundary bucket in their required lookback/volatility history. The registry says partial windows must not trigger signals. This is a contract-compliance defect affecting those 20 event records; the original report has not been recalculated or modified.

## 6. What the negative results establish

Sixteen of the 112 reported rows pass the 100-outcome sample-size gate. All 16 are momentum-continuation configurations. Every one has a negative gross mean before commission (range: -0.8310 to -0.4575 bps) and a session-clustered 95% interval whose upper bound is still negative (range of upper bounds: -0.6944 to -0.2663 bps). None beats NO_TRADE or ALWAYS_SHORT; 15 of 16 do not beat ALWAYS_LONG. One row (5-second lookback, threshold 1.0, 15-second horizon) beats ALWAYS_LONG on the reported gross comparison, but still has a negative gross mean and does not beat NO_TRADE or ALWAYS_SHORT.

No mean-reversion or breakout row passes the sample-size gate. Their results are insufficient to accept or reject those hypotheses.

Interpretation: the negative momentum result is reproducible from the raw quote data and is not explained by an entry/exit timing error, spread double subtraction, or a mismatch between the published report and the independent reconstruction. It is evidence against the registered momentum-continuation hypothesis on these four sampled windows. It is not a market-wide strategy verdict: the validation sample is short, the first-boundary-window contract issue affects 20 horizon records, the single-position filter has a latent edge case, commission is unverified, and quotes are not fills. No candidate is approved.

## 7. Required separately versioned corrections

Do not alter the original report, registry, plan, or validation artifact. A new implementation version should:
1. Mark boundary-partial feature windows and exclude them from every candidate lookback, scale, and compression calculation.
2. Enforce the single-position rule at signal time (`signal_window_end_msc < next_free`), not only at quote-entry time.
3. Count per-session skipped, attempted entry timeouts, and attempted exit timeouts during the sequential filter loop; do not infer skipped counts by subtracting all precomputed replay statuses.
4. Emit all 120 preregistered configuration/horizon rows, including explicit zero-signal rows.
5. Add synthetic tests for a signal emitted before the prior exit but whose first quote arrives after it, unresolved exits, per-session timeout accounting, zero-signal configurations, and first/last partial windows.
6. Clarify whether the one-position rule is per parameter+horizon simulation lane in a separately versioned plan amendment.

Any corrected implementation must be evaluated only on fresh, prospectively collected, untouched sessions under a new versioned preregistration. Do not rescore these same four dates to claim corrected performance. Keep the existing holdout sealed. Commission must be independently verified before net-performance evaluation. Execution remains disabled.
