# Phase 8 — market-session coverage proposal

**Status:** PROPOSAL ONLY — not an intake gate and not a change to the preregistered validation plan.

## Purpose

Distinct UTC collection dates protect chronological separation. They do not establish that the evidence samples the main intraday liquidity regimes. This supplemental proposal defines a reproducible way to classify timestamps and report session coverage without changing historical tick files or the existing four-date validation requirement.

## Timezone-aware session taxonomy

Store all source timestamps in UTC. Convert each timestamp using the IANA timezone database; do not hardcode a fixed UTC offset because London and New York change daylight-saving time on different dates.

| Label | Local timezone | Proposed local window | Interpretation |
|---|---|---|---|
| Asian | `Asia/Tokyo` | 09:00–18:00 | Tokyo daytime proxy for the Asian trading window |
| London | `Europe/London` | 08:00–17:00 | London business/trading day |
| New York | `America/New_York` | 08:00–17:00 | New York gold/FX trading day |
| London–New York overlap | Intersection of the London and New York UTC intervals | Computed daily | Explicit shared-liquidity window |

These are research classification windows, not exchange guarantees or claims that gold liquidity is uniform throughout each interval. The Tokyo window is a practical regional proxy; a future revision may add Hong Kong/Singapore as separate labels if the research design requires it.

For each UTC date, construct the London and New York intervals by converting their local start/end boundaries to UTC. Compute the overlap as the intersection of those UTC intervals. This automatically handles the weeks when the US and UK daylight-saving transitions are out of sync.

For 16 November 2026, the proposed windows convert to:
- Asian: 00:00–09:00 UTC
- London: 08:00–17:00 UTC
- New York: 13:00–22:00 UTC
- London–New York overlap: 13:00–17:00 UTC

## Classification contract

A derived session-coverage report should:
1. Read each manifest's UTC start/end and each tick's UTC timestamp.
2. Validate that timestamps are timezone-aware and monotonic; normalize to UTC.
3. Assign independent boolean labels. A tick may be both London and New York, and must additionally be marked overlap when inside the computed intersection.
4. Report collection-window intersection duration per label, tick counts per label, and first/last timestamp per label.
5. Keep raw CSV and original manifest immutable. Store classifications in a separate derived report that records source artifact IDs, source CSV SHA-256, classifier version, timezone database version, and generation timestamp.
6. Never infer missing market data from a session label; a label only describes when a quote was observed.

## Implemented supplemental reporter

A standalone, offline reporter now exists at `tools/mt5_xauusd_market_session_coverage.py`, with regression tests in `tests/test_mt5_xauusd_market_session_coverage.py`.

Example invocation against an already-downloaded collection artifact:

```bash
python -m tools.mt5_xauusd_market_session_coverage \
  --manifest path/to/manifest.json \
  --csv path/to/veltrix_exness_demo_ticks.csv \
  --output path/to/market_session_coverage.json \
  --source-artifact-id 14203352046 \
  --workflow-run-id 43814840356
```

The reporter verifies the source CSV SHA-256 against the manifest, checks XAUUSD identity, requires timezone-aware timestamps and monotonic tick order, reconciles `time_msc` with `time_utc`, and writes a separate JSON report. It records session counts, first/last ticks, actual collection-window intersection duration, source artifact/run identifiers when present, classifier version, and timezone database version. It never edits the source files or the intake catalog.

Regression coverage includes November standard-time windows, the UK/US daylight-saving mismatch, hash mismatch, naive timestamps, non-monotonic input, inconsistent epoch/ISO timestamps, and explicit artifact/run provenance. CI on PR #61 HEAD `6ad986610dfd1d490aa3d8934115519e6f3db18a` passed: 241 tests, Python compilation, and shell syntax validation. A subsequent provenance enhancement adds a seventh reporter test and requires a fresh CI run before that latest revision is treated as verified.

## Suggested coverage rule for review

If adopted, require at least 30 continuous minutes of actual collected data in each of the four labels across the validation evidence set. Count elapsed collection-window intersection, not merely tick count. A single collection may contribute to multiple labels only where its UTC interval genuinely intersects them. Report gaps and excluded/off-hours intervals explicitly.

This 30-minute-per-label rule is a proposal for owner review. It is not currently part of strict artifact intake, does not replace the four distinct UTC dates, and must not be silently enforced by the current catalog builder.

## Existing validation windows

| Session | UTC window | Classification under this proposal |
|---|---|---|
| validation_01 | 2026-11-13 10:23:27–10:53:29 | London (10:23–10:53 GMT) |
| validation_03 | 2026-11-15 23:14:45–23:44:47 | Outside proposed windows (18:14–18:44 EST; post-New York window) |
| validation_04 | 2026-11-16 06:10:18–06:40:20 | Asian (15:10–15:40 JST) |

Independent raw-artifact review corrected the earlier `validation_01` window transcription: it is 10:23–10:53 UTC, not 21:20–21:50 UTC. All three raw CSV hashes match their manifests. Reclassification of every tick under the stated IANA windows gives: `validation_01` — 3,857/3,857 London ticks; `validation_03` — 0 ticks in all four labels; `validation_04` — 11,537/11,537 Asian ticks. Across the three artifacts, London and Asian are represented; New York and London–New York overlap are not. `validation_03` is outside all proposed windows and must not be counted as New York-session coverage.

## Safety and scope

- No changes to the eligible session IDs, UTC-date validator, preregistered plan, or strict intake behavior.
- No edits to historical raw ticks or manifests.
- No strategy scoring, parameter tuning, candidate freeze, holdout access, or performance certification.
- Collector remains Exness DEMO, XAUUSD-only, manual, read-only, with trading and DLL imports disabled.


## Independent raw-artifact reclassification — 2026-11-16

The three eligible validation artifacts were downloaded from their original GitHub Actions runs and independently parsed. Each CSV SHA-256 matched its corresponding manifest.

| Session | UTC window | Raw ticks | Asian ticks | London ticks | New York ticks | Overlap ticks |
|---|---|---:|---:|---:|---:|---:|
| validation_01 | 13 Nov 10:23:27–10:53:29 | 3,857 | 0 | 3,857 | 0 | 0 |
| validation_03 | 15 Nov 23:14:45–23:44:47 | 4,035 | 0 | 0 | 0 | 0 |
| validation_04 | 16 Nov 06:10:18–06:40:20 | 11,537 | 11,537 | 0 | 0 | 0 |

Classification uses the proposal's 09:00–18:00 Tokyo, 08:00–17:00 London, and 08:00–17:00 New York local windows with IANA timezone conversion. Tick labels are descriptive only. These counts do not prove spread representativeness, trade execution quality, or strategy performance.


## Forward collector evidence improvement

The read-only collector now persists its periodic quote-validation snapshots in a separate `quote_validation_samples.csv` artifact. The manifest records the snapshot artifact filename, record count, byte count, and SHA-256. Each row carries both the collector observation time and the underlying MT5 quote timestamp, plus bid/ask, point size, spread points, and quote age. This separates risk-gate sampling from the full tick stream and makes future spread reconciliation reproducible. The historical validation_04 artifact remains unchanged; the new file applies to future collections only and is pending CI verification on the current PR head.
