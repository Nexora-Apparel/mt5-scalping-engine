

### 2026-11-20 — Dispatch-bound runtime metadata JSON extracted and verified

- **Run:** [44639446651](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44639446651), dispatch/head commit `09d9f58d8b755dc38c6d944094852997fe66af17`; job `135966384167` SUCCESS.
- **Artifact:** [14584443598](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44639446651/artifacts/14584443598), downloaded and extracted; ZIP contains `verification.json` (900-byte JSON payload). Artifact ZIP SHA-256 remains `92a37f4691f3cd3889ee465e0d0ceeb524fa161f601cc9ce97a19588be9a44a0`.
- **Runtime result:** `status=PASS`; `account_mode=DEMO`; source identifies authenticated Exness MT5 DEMO terminal.
- **DLL state:** `runtime.dlls_allowed=false`; `dll_imports_runtime_verified=true`; `dll_imports_enabled=false`. This confirms the effective runtime DLL-import state was explicitly false in this run.
- **XAUUSD contract:** canonical `XAUUSD` maps to broker symbol `XAUUSDm`; `currency_base=XAU`; `currency_profit=USD`; `point=0.001`; `contract_currency_metadata_verified=true`.
- **Versions:** terminal build `6327`; terminal version `[500, 6327, "19 Nov 2026"]`; MetaTrader5 Python integration `5.0.6231`.
- **Read-only flags:** `ticks_requested=false`, `trading_enabled=false`, `order_submission=false`, `position_management=false`, `credentials_recorded=false`.
- **Scope qualification:** This is a current, separate runtime attestation. It does not retroactively modify or upgrade the five legacy historical manifests; their historical-session DLL and contract metadata provenance remains explicitly limited.
- **Historical/prospective comparison:** Not yet computed. Existing five-window replay summaries establish historical descriptive metrics only; they are not a substitute for direct row-level comparison with prospective sessions. The previous data-analysis capability restriction remains in force; no alternate executor was used to bypass it. Consequently, no distributional comparison, session-matched spread delta, quote-age delta, or statistically established coverage deficiency is claimed here.
- **Known sampling footprint (not a deficiency verdict):** Five historical windows total 150 minutes across five UTC dates: Asia (9 Nov), overlap (6 and 11 Nov), New York (10 and 12 Nov). Prospective comparison inputs listed in the project record are `validation_01`, `validation_03`, `validation_04`, `validation_05`, and `validation_06` on 13, 15, 16, 17, and 18 Nov respectively. `validation_02` remains excluded as a duplicate UTC date. London historical attempts on 4 and 5 Nov returned zero ticks; 2 Nov also returned zero. Whether this creates a material mechanics-coverage gap cannot be concluded until the prospective data are compared on a session/time-of-day basis.
- **Decision:** Do not collect additional historical records yet. Preserve the existing artifacts and perform the pending quantitative comparison when the authorized data-analysis capability is available. Only then specify any collection gap by session, UTC date/time, quote count, timing distribution, spread distribution, and overlap status.
- **Result:** Runtime metadata verification **PASS**; direct historical-versus-prospective comparison **BLOCKED / NOT RUN**; additional collection **NOT AUTHORIZED BY EVIDENCE**.
- **Next action:** Resume a reproducible, session-matched comparison of the five historical CSV/manifest pairs against the five prospective session CSV/manifest pairs, retaining hashes and excluding duplicate UTC dates. Keep candidate scoring and all approval gates closed.


### 2026-11-20 — Comparison inputs re-staged; quantitative blocker isolated

- **Prospective inputs:** Re-listed the five approved distinct-date tick artifacts and successfully downloaded the ZIPs for local availability: `14029149674` (`validation_01`), `14185914411` (`validation_03`), `14203352046` (`validation_04`), `14335284843` (`validation_05`), and `14413428365` (`validation_06`). Their associated workflow runs are `43408593546`, `43773683398`, `43814840356`, `44096443341`, and `44270396480`.
- **Historical inputs:** Successfully downloaded the original V1 artifact `14420498746`, original V2 artifact `14422070722`, and combined quote-mechanics replay report artifact `14571079127`. The source historical artifacts remain immutable.
- **Artifact availability:** GitHub reported all eight requested archives as downloadable and not expired at retrieval time. This confirms availability only; it does not constitute inspection or quantitative comparison of their CSV contents.
- **Runtime metadata:** The separate JSON verification result recorded in the preceding entry remains PASS: effective DLL imports false; XAUUSDm contract XAU/USD; point 0.001; read-only flags false.
- **Quantitative blocker:** Direct row-level historical-versus-prospective analysis remains NOT RUN. The project constraint explicitly prohibits bypassing the unavailable data-analysis capability with an alternate executor. Artifact staging has been completed without extracting or analyzing tick CSV data through a substitute execution path.
- **Coverage conclusion:** No new deficiency has been quantitatively established. The known absence of historical London windows (Nov 4 and 5; Nov 2 also empty) and the 150-minute/5-date historical sample are recorded as candidate coverage limitations, not yet proven material gaps.
- **Decision:** No additional historical collection; no prospective schedule changes; no candidate scoring or tuning.
- **Next action:** When the authorized data-analysis capability is available, run a reproducible comparison using the eight staged source/replay archives. Match historical and prospective observations by UTC session/time-of-day; report row counts, duration, inter-arrival median/p95/max, stale intervals, bid/ask state changes, spread median/p95/max and coverage overlap. Preserve hashes and exclude `validation_02` from distinct-date evidence.


### 2026-11-20 — Authorized historical-versus-prospective tick comparison completed

- **Authorization and scope:** The owner explicitly lifted the prior alternative-executor restriction for this Phase 8 comparison only. Python was used for local, read-only ZIP/CSV/JSON extraction, integrity checks and descriptive statistics. No MT5 connection, broker API, order API, position API, holdout dataset, candidate scoring or candidate approval was used.
- **Inputs:** Prospective artifacts 14029149674 (validation_01, 13 Nov), 14185914411 (validation_03, 15 Nov), 14203352046 (validation_04, 16 Nov), 14335284843 (validation_05, 17 Nov), and 14413428365 (validation_06, 18 Nov). Historical source archives 14420498746 (V1) and 14422070722 (V2); replay artifact 14571079127 retained for provenance cross-check. validation_02 remains excluded as a duplicate UTC date.
- **Archive preservation:** All eight ZIPs were read without modification. ZIP SHA-256:
  - 14029149674: 5af056b78c4a61e3994a602bfa5682c6ca15e3c036768b703f984c084fe8b1eb
  - 14185914411: a8c0baff26a5fd1530bf1e91efcac462dbce6d31733aca38532d613ed5c4e140
  - 14203352046: b6c794fc62b5960d3cf0a3ce5d468df47a7702cc5eba4af3d97594bf79957597
  - 14335284843: b75f85ceb4366bf597bcae603a26053b6186d6cc97aac4ad0af907454f50ab0c
  - 14413428365: 1202ef6a28e74ff853753a431d74bb816e592972edf00e0fd53d2b159c722f55
  - 14420498746: 245b7997d6f9f33754916e6f028df712dd8bc0c2db8dc53c5ad361a1f18c8921 (matches previously recorded original)
  - 14422070722: 587d9e7533fa536469609bd20e0891391c0d8ca87ce35174a3c829aacfb328ee (matches previously recorded original)
  - 14571079127: 34b6c19618e5983609c6409a5b6542b42c0c4a21c8c016482203d90470e941a8 (matches previously recorded replay artifact)
- **CSV integrity:** All ten source CSVs matched their manifest SHA-256 and record counts. Timestamps were nondecreasing; every bid/ask pair was valid (bid > 0, ask >= bid); no window had a gap above five seconds.
- **Scope totals:** Historical 52,201 ticks over 149.966 minutes. Prospective 35,472 ticks over 149.979 minutes. These are separate 30-minute windows on distinct UTC dates, not continuous market coverage.
- **Window timing (median / p95 / max inter-tick gap, ms):**
  - Historical Asia 9 Nov 06:00 UTC: 138 / 1,047 / 2,290 (5,819 ticks).
  - Historical overlap 6 Nov 14:30 UTC: 28 / 277 / 1,724 (26,083 ticks).
  - Historical overlap 11 Nov 14:30 UTC: 62 / 687 / 2,135 (11,037 ticks).
  - Historical New York 10 Nov 17:30 UTC: 217 / 1,068 / 2,232 (4,836 ticks).
  - Historical New York 12 Nov 17:30 UTC: 227 / 1,135 / 2,220 (4,426 ticks).
  - Prospective validation_01, 13 Nov 10:23 UTC: 191 / 1,364 / 4,280 (3,857 ticks).
  - Prospective validation_03, 15 Nov 23:14 UTC: 222 / 1,263 / 4,873 (4,035 ticks).
  - Prospective validation_04, 16 Nov 06:10 UTC: 40 / 728 / 2,604 (11,537 ticks).
  - Prospective validation_05, 17 Nov 13:50 UTC: 64 / 944 / 1,877 (8,983 ticks).
  - Prospective validation_06, 18 Nov 08:50 UTC: 62 / 1,067 / 2,783 (7,060 ticks).
- **Session-level comparison (median / p95 inter-tick gap, ms; quote rate):**
  - Asia: historical 138 / 1,047; 3.23 ticks/s. Prospective 40 / 728; 6.41 ticks/s.
  - Overlap: historical pooled within windows 34 / 410; 10.31 ticks/s. Prospective 64 / 944; 4.99 ticks/s.
  - New York: historical pooled within windows 221 / 1,099; 2.57 ticks/s. No prospective 17:30–18:00 UTC New York window exists.
  - London: prospective 84 / 1,179; 3.03 ticks/s across 08:50 and 10:23 UTC windows. No successful historical London window exists.
  - validation_03 is a 23:14 UTC Sunday-reopen/off-hours sample (2.24 ticks/s), not a substitute for London or New York.
  - These are descriptive, non-date-matched session profiles, not statistical equivalence tests.
- **Spread:** Across all ten windows, median and p95 spread were approximately 240 points (0.240 raw XAUUSD price units at point 0.001). Maximum was 260 points in historical Asia/overlap/New York and prospective validation_04; all other prospective windows and historical 12 Nov New York maxed at 240. These are archived DEMO observations, not future spread or fill guarantees.
- **Quote age:** Periodic quote-validation snapshots exist only in prospective validation_05 and validation_06. validation_05 (1,798 samples): median 348 ms, p95 1,027 ms, max 1,669 ms; 106 samples >1 s, zero >2 s. validation_06 (1,799 samples): median 431 ms, p95 1,165 ms, max 2,196 ms; 199 samples >1 s, two >2 s. Neither had samples >5 s. Snapshot quote age is distinct from inter-tick gap; no quote-age snapshot evidence exists for the other eight windows.
- **Bid/ask state changes and flags:** 52,196 historical and 35,465 prospective adjacent-row bid/ask state changes. Historical raw flags are uniformly 134 (0x86, including undocumented 0x80); prospective flags are 6 (BID|ASK), except one BID-only row (2) in validation_01. Raw flags were preserved, not normalized.
- **Provenance limitation:** Prospective manifests identify authenticated Exness DEMO, XAUUSDm, point 0.001, DLL imports disabled and trading disabled. Historical manifests identify authenticated Exness DEMO, XAUUSDm, point 0.001 and terminal build 6324, but lack runtime-verified DLL-import state and structured XAU/USD contract currency metadata. The separate current runtime attestation (build 6327, DLL imports explicitly false, XAU/USD metadata verified) does not retroactively upgrade legacy historical manifests. Historical quotes are retrospective observations, not actual broker fills.
- **Specific coverage gaps established:** (1) Historical London coverage is absent while prospective London samples exist at 08:50 UTC (18 Nov) and 10:23 UTC (13 Nov). (2) Historical New York windows exist at 17:30 UTC on 10 and 12 Nov, but no prospective 17:30 UTC New York window exists; the Sunday-reopen sample is not a substitute. (3) Historical coverage remains only 150 minutes across five dates.
- **Conditional collection decision:** The comparison proves a targeted historical London-coverage gap. The narrow next backfill is limited to the two exact prospective London collector windows, using the existing bounded read-only batch workflow:
  - london_match_20261113_1023: 2026-11-13T10:23:27.444Z to 2026-11-13T10:53:29.444Z.
  - london_match_20261118_0850: 2026-11-18T08:50:56.378Z to 2026-11-18T09:20:58.416Z.
  Both are approximately 30 minutes, millisecond-aligned, distinct UTC dates, non-overlapping and below the 31-minute per-window limit. This enables same-date/time source comparison; it is not broad additional backfill.
- **Execution blocker:** The available GitHub connector exposes artifact download and repository read/write but no workflow-dispatch action. No new historical retrieval was triggered. The reviewed batch workflow requires the intervals_json workflow-dispatch input and existing DEMO credentials/signer pin. Manual dispatch is required for the two intervals above; never enter credential values in chat.
- **Decision:** No candidate scoring/tuning, holdout access, candidate freeze/approval/certification, order submission or position management occurred. DEMO-only execution restrictions and risk controls remain unchanged. No additional prospective collection was triggered.
- **Next action:** Dispatch only the two preregistered London historical intervals through .github/workflows/xauusd-historical-tick-batch.yml; then compare those historical CSVs with the exact prospective same-date/time windows. Separately add a prospective 17:30 UTC New York validation window only if balanced prospective session coverage remains required. Keep candidate/holdout/release gates closed.
