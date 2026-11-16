# Phase 8 — validation_04 independent raw-tick audit

**Audit status:** PASS WITH REVIEW ITEMS  
**Workflow:** [Run 43814840356](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43814840356)  
**Job:** 133124441861  
**Branch / source commit:** `phase8-distinct-validation-date-guard` / `2180d14a8f9aa33e4058d4defeeb0eda22265f82`  
**Session:** `validation_04`  
**Collection window:** 2026-11-16 06:10:18.572279–06:40:20.586814 UTC  
**Account:** Exness-MT5Trial10, manifest declares DEMO  
**Instrument:** XAUUSD, broker symbol XAUUSDm

## Artifact identity

- Tick artifact: `veltrix-exness-demo-ticks-14` (artifact ID 14203352046)
- Diagnostics artifact: `veltrix-exness-collector-diagnostics-14` (artifact ID 14203127574)
- Dataset: `veltrix_exness_demo_ticks.csv`
- CSV bytes: 1,451,085
- CSV rows: 11,537
- Independently recomputed SHA-256: `bec62f7a2521ecd9e9587a0a9292cdd0fa60aa7c4b24cdd423908e0cc464f589`
- Manifest SHA-256: identical
- Manifest status: PASS
- Duration: 1,802 seconds (30 minutes + 2 seconds)
- Quote-validation cycles: 1,798
- Trading enabled in collector manifest: false
- DLL imports enabled: false

## Independent raw CSV checks

The downloaded ZIP was opened and the CSV parsed independently, outside the workflow's own audit function.

| Check | Result |
|---|---:|
| Rows | 11,537 |
| Bid unique values | 8,513 |
| Ask unique values | 8,513 |
| Bid range | 3,839.284–3,864.891 |
| Ask range | 3,839.524–3,865.131 |
| Raw tick spread at 240 points | 11,536 rows |
| Raw tick spread at 260 points | 1 row |
| Spread anomaly timestamp | 2026-11-16 06:20:25.248 UTC |
| Spread anomaly bid / ask | 3861.965 / 3862.225 |
| Spread anomaly | 0.260 price units (260 points) |
| Manifest quote-cycle spread | min/mean/max 240 points across 1,798 samples |
| Non-zero last/volume/volume_real rows | 0 |
| Tick flags | 6 on all 11,537 rows |
| Maximum raw inter-tick gap | 2,604 ms |
| Gaps above 5 seconds | 0 |
| Non-monotonic timestamps | 0 |
| Repeated millisecond timestamps | 201 rows beyond first occurrence |

The raw tick CSV therefore contains one 260-point spread observation even though the manifest's separate quote-validation-cycle summary reports 240 points for every cycle. The two measurements have different sample counts (11,537 raw tick rows versus 1,798 validation cycles); preserve this discrepancy for review rather than silently treating the manifest summary as the complete tick-level spread distribution. The one wider tick is not an automatic rejection, but it should be reconciled against terminal diagnostics and subsequent sessions.

Bid/ask values vary. Tick flag 6 is consistent with bid/ask update flags; zero last/volume fields are not by themselves evidence of malformed data for a quote-only stream. Repeated millisecond timestamps are not equivalent to duplicate records; timestamps remained non-decreasing.

## Diagnostics and terminal evidence

- Terminal diagnostics identify MetaTrader 5 EXNESS x64 build 6320 and Exness Technologies Ltd.
- Terminal log reports synchronization with 0 positions and 0 orders.
- Terminal log also states: `trading has been enabled, demo account - hedging mode`. This describes terminal/account permission, not proof that the collector submitted orders. The workflow manifest says `trading_enabled=false`, the collector log states it contains no order-submission or position-management calls, and the workflow reports terminal defaults `Enabled=0`, `AllowLiveTrading=0`, `AllowDllImport=0`. Retain the distinction; do not interpret the terminal's account permission line as an order execution event.
- MetaEditor diagnostics contain 131 compile entries, each reporting 0 errors and 0 warnings.
- Diagnostic artifacts are sanitized; account login, password, and server values are redacted.

## Review items — do not silently waive

1. **Tick-level spread reconciliation:** one raw tick is 260 points while all 1,798 manifest quote-validation cycles report 240 points. Compare the exact timestamp with a per-cycle quote-validation CSV from a future collection and subsequent raw sessions. The validation_04 artifact bundle has no per-cycle quote CSV, and its terminal log has no tick-level quote records; the discrepancy cannot be closed from the available validation_04 diagnostics. Keep this as a review item, not an automatic session failure.
2. **Installer provenance:** workflow logs show the installer downloaded from `https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe`. The workflow log does not show Authenticode signature verification or comparison against an independently trusted hash. The terminal's product/company label is not a substitute for verifying the installer binary's signature and provenance.
3. **Execution-cost evidence:** tick spread is not commission evidence. Commission schedule, contract/lot-side fee, slippage, and execution latency remain separate requirements.
4. **Account evidence:** manifest and runtime identify a DEMO account, but retain the sanitized diagnostics and independently verify account identity evidence under the existing intake process. Terminal-level demo trading permission was enabled; collector-level execution remained disabled.
5. **Collection environment:** this was a GitHub-hosted Windows runner using a downloaded terminal installer. Treat it as an observed collection environment, not a trusted/pinned terminal build until provenance is resolved.

## Intake disposition

- Raw CSV SHA-256 matches the manifest.
- Structural, bid/ask, timestamp-order, and gap checks pass.
- Collection duration is 1,802 seconds and the UTC date (2026-11-16) is distinct from validation_01 (2026-11-13) and validation_03 (2026-11-15).
- This artifact may be submitted to strict four-session intake as `validation_04`, subject to the review items above being resolved or explicitly carried forward by the intake policy.
- This audit does not certify strategy performance, net profitability, realistic execution costs, commission, or readiness for live trading.
- Do not begin net scoring, candidate freeze, holdout, order execution, or live deployment on the strength of this artifact alone.

## Next steps

1. Collect `validation_05` on a further distinct UTC date (not 2026-11-13, 2026-11-15, or 2026-11-16).
2. Reconcile the one 260-point raw tick with terminal diagnostics and compare complete raw spread distributions across all eligible sessions.
3. Verify installer Authenticode publisher/signature and trusted provenance before marking runner software verified.
4. Obtain independent commission evidence and preserve the signed reviewer attestation and out-of-band trusted public-key fingerprint.
5. Run strict four-session intake only when validation_01, validation_03, validation_04, and validation_05 are all present and pass the date and evidence gates.

## Follow-up provenance check (2026-11-16)

The official Exness MT5 download page links its Windows installer directly to the `download.terminal.free` host, and its download link resolves to the same Exness-specific path observed in this workflow. This establishes that the host/path is linked from the official Exness download page; it reduces the earlier concern that the hostname was an unrelated third-party source.

It does **not** establish the authenticity or integrity of the particular installer bytes used by the GitHub runner. The workflow still lacks recorded Authenticode verification (valid signature, expected publisher, and certificate chain at download time) and a pinned independently trusted binary hash. Keep binary-level verification open until those checks are captured. The official page reference is https://www.exness.com/metatrader-5/ (download link labelled “Download MetaTrader 5”).


## Follow-up analysis — why raw tick and quote-cycle spread summaries differ (2026-11-16)

The collector source was inspected to identify the two measurement paths:

- Every collector loop calls `validate_quote(...)` and appends the returned `spread_points` to `spread_samples`. `validate_quote` obtains the latest snapshot through `mt5.symbol_info_tick(symbol)`.
- Separately, `_collect_symbol_ticks(...)` retrieves the tick stream through `mt5.copy_ticks_from(..., COPY_TICKS_ALL)`; the final CSV is built from those tick records.
- The loop sleeps for up to one second between quote snapshots. The raw tick stream can contain additional intermediate quote updates that are not represented in the periodic validation-snapshot sample.

Therefore the 1,798-cycle manifest spread summary and the 11,537-row raw-tick spread distribution are **different sampling populations**, not duplicate calculations over the same rows. The raw CSV independently confirms 11,536 observations at 240 points and one observation at 260 points (2026-11-16 06:20:25.248 UTC). The manifest's 1,798 quote snapshots report 240 points throughout. This is consistent with a short-lived wider raw tick occurring between periodic quote snapshots, but the existing manifest does not retain each quote snapshot's timestamp and bid/ask, so the precise correspondence cannot be proven retrospectively.

**Disposition:** classify the difference as an explained sampling-scope difference, while retaining the 260-point raw observation as genuine spread-distribution evidence. It is not evidence of CSV corruption or a hash mismatch. For future collections, retain each quote-validation snapshot (UTC timestamp, bid, ask, point size, spread points, and quote age) in a separate immutable artifact so periodic risk-gate observations can be reconciled directly against the full tick stream. Do not remove or normalize the 260-point tick.


## Forward collection instrumentation (2026-11-16)

The read-only collector now writes a separate `quote_validation_samples.csv` containing one row per periodic quote-validation cycle, including observation UTC, underlying quote timestamp, bid/ask, point size, spread points, and quote age. Its row count, byte count, and SHA-256 are recorded in the manifest under `quote_validation_dataset`. This preserves the periodic risk-gate sample separately from the complete `COPY_TICKS_ALL` raw tick stream and allows future collections to reconcile the two datasets by timestamp without changing or rewriting historical artifacts. The collector remains XAUUSD-only, DEMO-only, trading-disabled, and DLL-disabled. The new instrumentation and regression test passed Project tests workflow run `43939726288` on commit `5575a01231fd2ea67127a80b3a7f9cea0467c796` (242 tests passed). No new live MT5 collection has yet exercised this artifact.
