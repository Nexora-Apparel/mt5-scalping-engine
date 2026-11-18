# Phase 8 — accelerated validation research and redesign

**Repository:** `Nexora-Apparel/mt5-scalping-engine`  
**Research date:** 2026-11-17  
**Current branch:** `phase8-distinct-validation-date-guard`  
**Current PR:** #61 — draft, open, unmerged  
**Scope:** XAUUSD only; Exness MT5 DEMO; research and read-only collection only.

## Executive decision

The eight-future-date wait is not the only defensible route. The best acceleration is a **hybrid historical-replay + short prospective DEMO verification design**:

1. First probe the connected Exness MT5 server for historical XAUUSD ticks using MetaQuotes' official Python `copy_ticks_range` API.
2. If adequate history is available, backfill multiple preselected UTC dates and session windows in one workflow run. Preserve every source date separately and label the dataset as historical replay, not as a live prospective collection.
3. If MT5 history is unavailable or incomplete, test Exness' public Tick History archive as a separate historical source. Do not silently treat it as the exact MT5 DEMO server feed.
4. Run the unchanged candidate registry over a chronological, leakage-controlled historical dataset, with date/session dependence and multiple-testing corrections.
5. Keep a short live DEMO read-only shadow capture for current feed, spread, quote-age, gap, terminal and operational checks. This operational check does not need to wait for eight future calendar dates.
6. Preserve the final holdout sealed until the candidate selection record is committed.

This can remove most of the calendar delay **if the broker's historical tick endpoint returns adequate data**. It does not make a strategy profitable by assumption, create independent observations by resampling, or remove the need to verify commissions and execution costs.

## 1. What the current experiment actually requires

The current v2 plan is stricter than the informal description of "eight more sessions":

- It requires 12 eligible validation sessions on 12 distinct UTC dates: the existing four eligible dates plus `validation_06` through `validation_13`.
- Each additional collection is intended to be at least 1,800 seconds.
- The evaluator requires at least 100 outcomes per candidate configuration/horizon.
- The final holdout requires 10 sessions on 10 distinct dates and at least 300 outcomes per candidate configuration/horizon.
- Candidate definitions, parameter grids, bid/ask crossing, benchmark set and slippage grid are locked.
- Commission is still unverified, so net performance is blocked.
- The existing v1 result rejected all 112 candidate/horizon rows; no candidate is approved.

The eight future dates are therefore a design choice in plan v2, not a universal law of financial statistics. They must not be bypassed by falsely counting multiple same-day sessions as separate dates. A separately versioned plan can use a different data-acquisition design while preserving the original v1 and v2 records.

## 2. Important defects in the current v2 execution path

### 2.1 New session IDs are rejected by the collector

The collection workflow dropdown exposes `validation_06`–`validation_13`, but `tools/mt5_demo_tick_collector.py` currently allowlists only:

- `validation_01`
- `validation_03`
- `validation_04`
- `validation_05`

The collector will reject a new v2 session ID before collection begins. The existing v2 test checks that the workflow dropdown exposes the IDs, but does not assert that the collector accepts them. Add an explicit test that the workflow input choices, collector allowlist and plan validation IDs agree.

### 2.2 Two scheduled dates are market-closed

The current proposed schedule places:

- `validation_09` on Saturday, 21 November 2026 at 06:00 UTC.
- `validation_10` on Sunday, 22 November 2026 at 10:00 UTC.

Exness' post-US-DST schedule lists ordinary XAUUSD as closed all Saturday and closed on Sunday until 23:05 UTC. Those two target windows cannot produce normal XAUUSD trading ticks. Do not substitute XAUUSD247: it is a different instrument with separate weekend pricing and a special price offset.

### 2.3 The overlap windows are one hour early

The current schedule labels 13:30–14:00 UTC as London–New York overlap. After the US daylight-saving change on 1 November 2026, Exness lists New York's winter opening at 14:30 UTC. A 13:30–14:00 UTC capture is pre-overlap. Move overlap targets to 14:30–15:00 UTC (15:30–16:00 WAT) if retaining the live schedule.

### 2.4 Current CI evidence

The current PR head at research time is `6f41d983d3df90cdb97ce11ca38a3de374d55c7b`. Its GitHub Actions `python-tests` check completed successfully in run `44120419053`. That establishes the tested Python check passed; it does not prove that the collector can successfully retrieve new sessions from Exness or that the current schedule is executable.

## 3. Preferred accelerator: MT5 historical tick backfill

MetaQuotes' official Python integration exposes:

```python
mt5.copy_ticks_range(symbol, date_from, date_to, mt5.COPY_TICKS_ALL)
```

It returns tick records with time, bid, ask, last, flags and millisecond timestamps. MetaQuotes specifies that request datetimes should be UTC-aware because MT5 stores tick and bar times in UTC. The terminal may return `None` on failure; the caller must inspect `last_error()`.

The existing Windows workflow already installs the Exness MT5 terminal, authenticates using repository secrets, installs the pinned MetaTrader5 Python package and uses read-only terminal permissions. A separate historical-backfill job can therefore test the server's historical tick availability without introducing order execution.

### 3.1 Feasibility probe — first operation

Before changing the formal plan, add a bounded diagnostic mode that requests a small historical interval for the exact broker symbol resolved by the current DEMO account (currently observed as `XAUUSDm`).

The probe should:

1. Verify the expected Exness account identity and DEMO trade mode.
2. Resolve the exact XAUUSD broker symbol from the account's symbol catalogue; do not hardcode an assumed suffix.
3. Request a short UTC interval from a known completed collection date, ideally overlapping `validation_05`.
4. Compare the returned history with the already preserved live tick CSV for the same interval.
5. Report returned count, timestamp coverage, duplicate rate, ordering, maximum gaps, bid/ask validity and exact overlap-match ratio.
6. Record terminal build, MetaTrader5 package version, broker server, symbol specification, requested UTC interval, retrieval time, raw-file SHA-256 and all errors.
7. Keep trading, DLL imports, order submission and position management disabled.

This comparison is critical. Historical data should not be accepted merely because the API returns a non-empty array. The historical feed must be reconciled against the known live capture, and missing or truncated intervals must fail closed.

### 3.2 Batch historical replay

If the probe passes, add a separate workflow that requests a preregistered list of date/time intervals in one run. It can download many historical dates in one terminal session; the dates do not need to be collected live one day at a time.

The output must use a distinct manifest schema and clearly separate:

- `market_interval_start_utc` / `market_interval_end_utc`: the historical period represented;
- `retrieved_at_utc`: when the backfill was downloaded;
- `source_type`: broker-terminal historical ticks;
- `account_mode`: verified DEMO account used to access the terminal;
- `broker_server` and exact broker symbol;
- `requested_interval`, actual first/last tick, tick count and coverage;
- data SHA-256 and manifest SHA-256.

Do not copy the live collector's `duration_clock=monotonic` field onto a historical data request. Download time is not market observation time. Do not claim a historical interval was a live 30-minute collection.

### 3.3 Historical date selection

Select dates before opening or evaluating their outcomes. Use a spread across multiple weeks and weekdays, and stratify windows across Asian, London, London–New York overlap and later New York trading. Exclude weekends and market holidays for ordinary XAUUSD.

The historical sample should be materially broader than eight 30-minute snippets if available. Prefer complete session windows or longer contiguous segments, because very short cherry-picked intervals can omit quiet periods, spread widening, rollover effects and volatility transitions.

The data selection manifest must be committed before the replay report is generated. Candidate registry and parameter grids remain unchanged. If a date was previously used for candidate design, manual inspection, debugging or parameter selection, disclose that fact and do not present it as untouched holdout evidence.

## 4. Secondary source: Exness public Tick History archive

Exness publishes a Tick History interface with historical bid and ask quotes. Its official blog states that historical quotes are available for strategy research and can be downloaded without a trading account; it describes millisecond-level records and archive history going back to 2015. The archive page itself describes the data as indicative and informational, not execution records.

Important limitation: Exness' Help Center says the archive draws ticks from specified MT4 real servers and that the user cannot choose the server; ticks from different servers can differ slightly due to timing/latency. The public archive therefore cannot automatically be treated as identical to the user's MT5 DEMO `XAUUSDm` stream.

Use this source as a separate **Exness historical quote research dataset**, with its own provenance and data-quality tests. Do not merge it invisibly into the MT5 DEMO feed. If the exact Standard-account `XAUUSDm` instrument is available in the archive, verify its contract/suffix and compare an overlapping date with the MT5 DEMO capture before use.

It can accelerate historical price-action and spread research. It cannot establish actual order fills, the user's account-specific execution latency, slippage or commission.

## 5. Third source: external tick history

Dukascopy provides historical XAUUSD tick data with bid/ask quotes and millisecond timestamps. It is useful as a cross-provider robustness check and for broad market-regime coverage.

It is not a replacement for Exness data. Broker feeds can differ in quote timing, spread, price construction, liquidity and execution. An external-feed result should be reported as external-feed robustness, not Exness execution performance.

## 6. Statistical design: how to use the additional data correctly

### 6.1 Sessions within one date are not independent dates

Asian, London and New York sessions on the same date provide different intraday liquidity regimes, but they share that day's macroeconomic shocks, news, market positioning and broad volatility environment. Counting them as three independent daily clusters would understate uncertainty.

The dataset should retain both levels:

- observation/session level for intraday analysis;
- UTC-date level for dependence-aware inference.

Where multiple sessions are collected per date, aggregate or resample at the date cluster for the primary confidence interval. A secondary session-block analysis can describe conditional intraday behaviour, but must not be described as independent day-to-day replication.

### 6.2 Use dependence-aware resampling

Politis and Romano's stationary bootstrap resamples consecutive blocks of weakly dependent observations with random block lengths. This preserves local serial dependence better than resampling individual ticks or individual trades independently.

For VELTRIX, apply a block method to the time-ordered strategy outcome series, not to randomly shuffled tick rows. Preserve session boundaries and avoid stitching unrelated market periods together without a declared regime model. Choose block lengths through a predeclared sensitivity analysis.

A block bootstrap cannot create new market regimes or replace genuinely unseen dates. With only one date, it can estimate within-sample temporal variability, not reliable day-to-day generalization.

### 6.3 Account for a small number of date clusters

Cluster-robust inference assumes independence across clusters and allows dependence within each cluster. The econometrics literature warns that conventional cluster-robust inference can be unreliable with few clusters; bootstrap methods such as restricted wild-cluster bootstrap can improve some finite-sample tests, but do not manufacture independent information.

Use date-clustered confidence intervals as the primary method where enough dates exist. Report the number of date clusters explicitly. With too few dates, label the inference exploratory and do not approve the candidate.

### 6.4 Correct for the 112-row search universe

The baseline report evaluates 112 configuration/horizon rows. Selecting the best-looking row after inspecting all results creates data-snooping and multiple-testing bias.

Use a preregistered primary comparison and a family-wise strategy-universe test such as Hansen's Superior Predictive Ability (SPA) test or White's Reality Check, with dependence-preserving bootstrap resampling. The Deflated Sharpe Ratio can be a supplementary selection-bias/non-normality diagnostic if Sharpe-based claims are reported.

Do not tune the strategy using the new validation set. Do not repeatedly inspect results and stop at the first favourable p-value without a predeclared sequential-testing rule.

### 6.5 Chronological walk-forward and sealed holdout

Use a strict chronological split. All feature construction must be causal. Apply the existing 120-second partition purge and ensure that no label horizon or lookback window crosses a partition boundary. No random row split.

The validation data can be used only for the already registered candidate selection rule. Once a candidate is selected, commit a selection-freeze record containing the registry hash, validation report hash, timestamp, selection rule and selected configuration IDs. The timestamp must precede any access to the final holdout data.

The holdout must remain separate and unscored until that freeze is committed. Historical backfill does not justify opening or tuning against the holdout.

## 7. Execution-cost and operational limits

Tick quotes are not broker fills. The current evaluator uses theoretical bid/ask quote crossing and has no actual market-impact or fill evidence. Exness itself warns that historical quotes do not show individual trade executions.

Before any net-performance claim:

- verify the applicable Exness DEMO commission/fee schedule or account statement;
- retain the registered slippage sensitivity grid;
- account for spread exactly once;
- measure quote age, gaps and observed spreads by session;
- run a separate, explicitly authorized DEMO execution rehearsal only after the execution safety gates are implemented and verified.

The current Phase 8 collector remains strictly read-only. This research does not authorize changing it to submit orders or manage positions.

## 8. Recommended implementation sequence

| Order | Work item | Expected result |
|---:|---|---|
| 1 | Fix collector allowlist/test mismatch and add schedule validation against Exness XAUUSD hours | Existing live workflow becomes executable only for valid IDs/windows |
| 2 | Add a one-interval MT5 historical tick probe | Determine whether the connected Exness MT5 server supplies usable historical ticks |
| 3 | Compare historical ticks against the preserved `validation_05` live capture | Establish source parity/limitations |
| 4 | If probe passes, add a separate batch historical-backfill workflow and manifest schema | Obtain multiple historical dates in one run |
| 5 | Create a separately versioned historical-replay plan; leave v1 and v2 immutable | Explicitly distinguish retrospective replay from prospective replication |
| 6 | Run unchanged candidate registry with chronological partitions, date-clustered/block-bootstrap inference and multiple-testing correction | Accelerated research evaluation |
| 7 | Keep one or more short live DEMO read-only captures for current feed/operations | Verify present-day quote and terminal behaviour |
| 8 | Verify commissions, reviewer attestation, signer pinning and manual reactivation rehearsal | Complete independent release gates |
| 9 | Freeze candidate selection before opening sealed holdout | Preserve unbiased final assessment |

## 9. If historical backfill is unavailable

Use the corrected live schedule across eight **trading weekdays**, not eight consecutive calendar days:

| Session | UTC date | UTC window | Coverage |
|---|---|---|---|
| validation_06 | 18 Nov 2026 (Wed) | 06:00–06:30 | Asian |
| validation_07 | 19 Nov 2026 (Thu) | 10:00–10:30 | London |
| validation_08 | 20 Nov 2026 (Fri) | 14:30–15:00 | London–New York overlap |
| validation_09 | 23 Nov 2026 (Mon) | 06:00–06:30 | Asian |
| validation_10 | 24 Nov 2026 (Tue) | 10:00–10:30 | London |
| validation_11 | 25 Nov 2026 (Wed) | 14:30–15:00 | London–New York overlap |
| validation_12 | 26 Nov 2026 (Thu) | 17:30–18:00 | New York after London close |
| validation_13 | 27 Nov 2026 (Fri) | 10:00–10:30 | London |

All times are UTC; add one hour for WAT. These are target windows only; actual manifest timestamps govern classification. The schedule is a fallback, not the preferred accelerator.

## 10. Sources

1. MetaQuotes, Python `copy_ticks_range`: https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py
2. MetaQuotes, MQL5 `CopyTicksRange`: https://www.mql5.com/en/docs/series/copyticksrange
3. Exness, Tick History archive: https://www.exness.com/tick-history/
4. Exness Help Center, Tick History provenance and limitations: https://get.exness.help/hc/en-us/articles/360021547851-Tick-history
5. Exness Help Center, Instrument trading hours (updated 14 November 2026): https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours
6. Exness, US DST trading-hours update (1 November 2026): https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026
7. Politis and Romano (1994), “The Stationary Bootstrap,” Journal of the American Statistical Association: https://doi.org/10.1080/01621459.1994.10476870
8. MacKinnon, Nielsen and Webb (2023), “Cluster-robust inference: A guide to empirical practice,” Journal of Econometrics: https://doi.org/10.1016/j.jeconom.2022.04.001
9. White (2000), “A Reality Check for Data Snooping,” Econometrica: https://doi.org/10.1111/1468-0262.00152
10. Hansen (2005), “A Test for Superior Predictive Ability”: https://doi.org/10.1198/073500105000000063
11. Bailey and López de Prado (2014), “The Deflated Sharpe Ratio”: https://doi.org/10.3905/jpm.2014.40.5.094
12. Zhang and Hua (2025), “Major Issues in High-Frequency Financial Data Analysis: A Survey of Solutions”: https://doi.org/10.3390/math13030347

---

**Final research conclusion:** The preferred route is not to pretend that one day equals eight days. It is to retrieve genuinely historical, timestamped XAUUSD ticks in one batch, test their provenance and completeness against the existing Exness DEMO capture, and run a separately versioned historical replay with proper chronological and dependence-aware inference. Keep the short live DEMO verification separate. This is the fastest credible route if the broker history probe passes; if it fails, use the corrected weekday schedule rather than the current weekend/incorrect-overlap schedule.
