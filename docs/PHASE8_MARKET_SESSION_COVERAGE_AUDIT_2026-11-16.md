# Phase 8 — independent market-session coverage audit

**Audit date:** 2026-11-16  
**Scope:** Descriptive classification of existing validation raw ticks only  
**Status:** PASS for source-integrity and timestamp classification; coverage incomplete  
**Policy effect:** None. This is supplemental evidence, not a new intake gate.

## Method

Downloaded the original tick ZIP artifacts from their GitHub Actions runs, extracted the CSV and manifest, recomputed SHA-256 over the exact CSV bytes, and independently parsed every row. Each CSV hash matched its manifest. Every tick's `time_utc` was converted through IANA `Asia/Tokyo`, `Europe/London`, and `America/New_York` timezones.

Classification windows follow the proposal:
- Asian proxy: Tokyo local 09:00–18:00.
- London: London local 08:00–17:00.
- New York: New York local 08:00–17:00.
- London–New York overlap: simultaneous membership in the London and New York windows.

Intervals are start-inclusive/end-exclusive. UTC remains the canonical stored time. Tick counts are observations, not volume or executions.

## Artifact-level results

| Session | Workflow run | Tick artifact | UTC collection window | Ticks | SHA-256 |
|---|---:|---:|---|---:|---|
| validation_01 | 43408593546 | 14029149674 | 13 Nov 10:23:27.444788–10:53:29.444946 | 3,857 | `2c49c75922480d36be8c6e5cfbde4328d3c2154174df289a957074d61c969fb5` |
| validation_03 | 43773683398 | 14185914411 | 15 Nov 23:14:45.087447–23:44:47.061410 | 4,035 | `15e5066e687157fd9a5bbc1e66c3fc6fb2833693638a9c7010186d5d4096eb25` |
| validation_04 | 43814840356 | 14203352046 | 16 Nov 06:10:18.572279–06:40:20.586814 | 11,537 | `bec62f7a2521ecd9e9587a0a9292cdd0fa60aa7c4b24cdd423908e0cc464f589` |

All three hashes matched their respective manifests.

Derived machine-readable output for `validation_04` is stored at `research/session-artifacts/validation_04_market_session_coverage.json`. It binds the original CSV SHA-256, workflow run `43814840356`, and tick artifact `14203352046`; the original source CSV and manifest remain unchanged.

## Tick classification

| Session | Asian | London | New York | London–New York overlap |
|---|---:|---:|---:|---:|
| validation_01 | 0 | 3,857 | 0 | 0 |
| validation_03 | 0 | 0 | 0 | 0 |
| validation_04 | 11,537 | 0 | 0 | 0 |
| **Total** | **11,537** | **3,857** | **0** | **0** |

The complete 30-minute validation_01 sample falls inside the proposed London window. The complete validation_04 sample falls inside the proposed Asian window. validation_03 falls outside all four proposed labels; it is after the defined New York local window and must not be described as New York-session evidence.

## Coverage disposition

- Asian: represented by one 30-minute validation window.
- London: represented by one 30-minute validation window.
- New York: not represented.
- London–New York overlap: not represented.
- validation_03 remains valid historical raw evidence under the existing date-based intake policy; its off-window classification does not invalidate it.
- The 30-minute-per-label proposal remains unapproved and does not change the four-distinct-UTC-date rule.

## Next collection targeting

The missing coverage is New York and the London–New York overlap. A future supplemental collection should target a window that genuinely intersects both defined local windows, with its exact UTC interval derived from IANA zones on the collection date. Do not relabel validation_03 or rewrite historical timestamps to fill this gap.

## Limitations

This audit does not establish representative liquidity, executable spread, commission, slippage, latency, profitable strategy behaviour, or certification. The separate raw-spread discrepancy and installer provenance review items remain open. No orders were submitted or managed.


## validation_05 targeting recommendation — 2026-11-17

The next eligible validation date can also close the remaining market-session coverage gap; a separate supplemental collection is not inherently necessary. For 17 November 2026, the UK is on GMT (UTC+0) and New York is on EST (UTC-5). Under the documented local windows (London 08:00–17:00 and New York 08:00–17:00), their overlap is 13:00–17:00 UTC.

**Recommended validation_05 window:** 2026-11-17 13:30–14:00 UTC (14:30–15:00 WAT). This is a 30-minute collection wholly inside both the New York proxy and London–New York overlap, on a UTC date distinct from validation_01 (13 Nov), validation_03 (15 Nov), and validation_04 (16 Nov). It preserves the four-date intake policy while targeting the actual evidence gap. It does not guarantee market representativeness or certify execution quality.

This is a scheduling recommendation, not a dispatched or completed collection. The GitHub workflow still requires manual dispatch by the repository owner. If market hours, broker availability, or current session conditions differ, record the actual UTC start/end times and classify the observed window; do not backdate or relabel it.
