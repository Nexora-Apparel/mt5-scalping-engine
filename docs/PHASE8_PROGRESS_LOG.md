# Phase 8 — engineering progress and decision log

**Repository:** `Nexora-Apparel/mt5-scalping-engine`  
**Pull request:** [#61](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/61)  
**Working branch:** `phase8-distinct-validation-date-guard`  
**Last recorded repository state:** 2026-11-17  
**Scope:** XAUUSD only; authenticated Exness MT5 DEMO; read-only research and data collection.

> This is the living project log. Append dated entries when implementation, evidence, decisions, or blockers change. Distinguish code written from code tested, and distinguish a completed research run from strategy approval.

## 1. Current project state

- PR #61 is open, draft, and unmerged.
- The historical-probe implementation is currently recorded through commit `996d95088c628879349ef7c1d2335f188f868c1d`; the progress-log update itself will create a later PR head.
- `main` contains a narrowly scoped manual dispatcher at `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` (latest dispatcher commit `bb7c97fe66c7f6f44e4a9d38d07f3080662db9c1`). It checks out the fixed Phase 8 PR branch; it does not merge PR #61 or copy the strategy implementation into `main`.
- Four eligible live validation sessions are preserved across four distinct UTC dates:
  - `validation_01` — 2026-11-13
  - `validation_03` — 2026-11-15
  - `validation_04` — 2026-11-16
  - `validation_05` — 2026-11-17
- `validation_02` is retained as audit evidence but excluded from eligible date count because it duplicates the UTC date of `validation_01`.
- The v1 baseline research evaluation completed, but **no candidate was approved**.
- The final holdout remains sealed.
- Historical MT5 tick retrieval is being investigated as a way to reduce calendar waiting without misrepresenting retrospective data as prospective collection.

## 2. Why the Phase 8 approach changed

The original prospective v2 design adds eight future 30-minute sessions on eight distinct UTC dates. Review identified that the proposed schedule included market-closed weekend windows and overlap windows one hour early after the US daylight-saving transition.

A separate research review proposed a faster, evidence-preserving alternative:

1. Probe historical XAUUSD ticks from the authenticated Exness MT5 terminal.
2. Compare an overlapping historical interval with the already verified `validation_05` live tick capture.
3. If source quality and coverage are adequate, build a separately versioned historical-replay dataset and plan.
4. Keep a short live DEMO read-only capture for present-day terminal/feed operation.
5. Preserve chronological evaluation, date/session dependence controls, multiple-testing safeguards, commission verification, and the sealed holdout.

This is an acceleration of data acquisition, not a shortcut to approval. Historical quote records are not broker fills and cannot prove account-specific execution, slippage, or commission.

Detailed research and source references: [PHASE8_ACCELERATED_VALIDATION_RESEARCH.md](PHASE8_ACCELERATED_VALIDATION_RESEARCH.md).

## 3. Work completed or recorded

| Work item | What changed / evidence | Reason |
|---|---|---|
| Distinct-date eligibility | Kept `validation_02` excluded from eligible count; four distinct eligible UTC dates remain | Multiple sessions on one date must not be represented as independent dates |
| Collector session allowlist | Extended accepted IDs to `validation_01` and `validation_03`–`validation_13` | The v2 workflow exposed IDs that the collector previously rejected |
| Collector tests | Updated accepted-ID coverage and added rejection coverage for `validation_14` | Prevent unregistered collection IDs |
| Historical tick probe | Reworked as V2: inclusive UTC millisecond bounds, one-minute non-overlapping requests, strict tick-field validation, duplicate removal, chronological-order checks, atomic CSV publication, shared dataset audit, SHA-256 and source provenance | Prevent silent truncation/partial output and make historical evidence auditable |
| Historical probe tests | Expanded `tests/test_mt5_xauusd_historical_tick_probe.py` for offset normalization, chunk boundaries, endpoint inclusion, duplicate removal, malformed/out-of-range ticks, non-monotonic responses, DEMO rejection, empty results and API errors | Exercise the probe's fail-closed paths before any broker request |
| Manual probe workflow | Added PR-branch workflow `.github/workflows/xauusd-historical-tick-probe.yml` and a default-branch dispatcher `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` | GitHub requires the manual-dispatch workflow to exist on the default branch; dispatcher checks out the fixed PR branch without merging it |
| PR activity record | Added a PR comment describing the probe implementation and intended first comparison interval | Preserve implementation context and avoid implying that the probe has already run |
| Research redesign | Added `docs/PHASE8_ACCELERATED_VALIDATION_RESEARCH.md` | Evaluate a faster route without weakening statistical or safety gates |

**Important status distinction:** These entries record implementation and repository evidence. They do not, by themselves, mean the new historical probe has run, that source parity has been established, or that all tests for the newest commit have passed.

## 4. Baseline evidence — not approved

Formal v1 evaluation:

- Workflow run: [44112391721](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44112391721)
- Job: `134141209101`
- Artifact: `14340019644`
- Report SHA-256: `677818dd2b2b266dfce3ce280277de89684fb270fa238e22e86b2ce62df00931`
- Status: `RESEARCH_EVALUATION_COMPLETE`
- Candidate approval: `NOT_APPROVED`
- Candidate/horizon rows: 112; all 112 not approved
- No configuration had a date/session-clustered 95% confidence interval lower bound above zero.
- Commission remained unverified; net performance was blocked.
- Outcomes were theoretical bid/ask quote marks, not actual broker fills.
- Holdout eligibility remained false.

Interpretation: this was a research rejection of the current candidate set on the available sample, not a collection or CI failure. Do not tune the frozen candidate registry against this result.

## 5. Current implementation review findings

A source inspection identified and the implementation has now addressed these defects:

1. **CSV/manifest newline escaping:** corrected to real newline characters; tests assert the CSV does not contain escaped backslash-n records and the manifest ends with a newline.
2. **Default terminal path:** corrected to `C:\\MT5\\terminal64.exe`, matching the collector's Windows path convention.
3. **Probe/collector helper contract:** the probe uses the collector's `connect_expected_account`, `discover_symbol`, `utc_iso`, `validate_account`, `audit_ticks`, and `DEMO_TRADE_MODE`; the focused tests stub the account and broker helpers. Runtime integration against Exness remains untested.
4. **Retrieval completeness and ordering:** replaced the fragile 10,000-record cursor loop with one-minute, inclusive, non-overlapping UTC millisecond windows. Each chunk is independently requested; out-of-range, malformed, and backwards-ordered responses fail closed. The final CSV is audited using the collector's shared audit routine before its manifest is published.
5. **Workflow dispatch availability:** resolved with a dedicated dispatcher committed to `main`. It has only `contents: read`, checks out the fixed `phase8-distinct-validation-date-guard` branch with persisted credentials disabled, records the exact checked-out commit, and runs focused preflight tests before installing MT5 or using secrets. PR #61 remains unmerged.
6. **Signer trust:** Authenticode validity, MetaQuotes Ltd. publisher identity, and Code Signing EKU are checked by the workflow. Independent pinning of the signer thumbprint against Exness-controlled evidence is still outstanding.

The focused preflight tests are wired into the dispatcher, but have not yet been observed passing on GitHub Actions. Do not start a broker probe until the preflight succeeds. Independent installer signer-thumbprint pinning against Exness-controlled evidence remains outstanding.

## 6. Next implementation sequence

| Order | Next action | Completion evidence |
|---:|---|---|
| 1 | Complete code review of the V2 probe and focused tests | Source review plus passing preflight run |
| 2 | Execute focused tests through the main-branch dispatcher preflight | Passing pytest output tied to the checked-out PR commit |
| 3 | Verify manual dispatcher, branch pinning, permissions, and secret boundaries | Workflow run reaches preflight and does not proceed if tests fail |
| 4 | Run the full repository Python tests, compilation, and shell syntax checks | Successful CI run tied to the exact PR HEAD |
| 5 | Provide the owner the direct Actions link and exact input instructions when the workflow is genuinely dispatchable | Manual run instructions with the exact UTC interval |
| 6 | Run the historical probe over the exact `validation_05` overlap interval | Completed run and downloadable raw CSV/manifest artifact |
| 7 | Compare historical results against the preserved live `validation_05` capture | Counts, coverage, timestamp/quote matching, gaps, spread and hash report |
| 8 | If source quality passes, design a separately versioned historical replay plan before evaluating results | Preregistered plan and immutable input manifest |
| 9 | Run unchanged candidates with chronological partitions and dependence/multiple-testing controls | Research report; no automatic candidate approval |
| 10 | Keep live read-only verification and all independent release gates separate | Explicit evidence for each gate |

## 7. Manual execution handoff format

When a manual action is required, the project update must contain:

- Direct GitHub Actions workflow URL.
- Exact workflow name and button to press.
- Exact `from_utc` and `to_utc` values to enter.
- Expected run name and success/failure indicators.
- Exact artifact name to download.
- Instruction to upload the artifact back into this conversation for integrity and source-parity review.

Do not ask the owner to inspect code, edit workflow YAML, or supply credentials in chat. Credentials remain in GitHub Actions secrets.

## 8. Safety and release gates — unchanged

- Historical probe and collector are read-only.
- XAUUSD only; DEMO account identity must be verified.
- No order submission, position management, or live/real-money execution in this workflow.
- Terminal trading and DLL permissions remain disabled by the collector workflow.
- No weakening of account identity, installer signature, or read-only controls.
- No candidate freeze, holdout access/scoring, performance certification, production deployment, or real-money trading until the relevant gates are independently satisfied.
- Outstanding evidence includes applicable Exness commission/fee verification, independent reviewer attestation, out-of-band Ed25519 fingerprint verification, independent signer-thumbprint pinning, and manual owner-controlled DEMO reactivation rehearsal.

## 9. Append-only update template

Use this format for each material change:

### YYYY-MM-DD — Short change title

- **Starting commit / PR head:**
- **Files changed:**
- **What changed:**
- **Why it changed:**
- **Tests and exact run links:**
- **Evidence/artifact IDs and hashes:**
- **Result:** PASS / FAIL / BLOCKED / NOT RUN
- **Remaining risks or blockers:**
- **Next action:**

Never overwrite a failed result with a later success. Record the later success as a new entry and retain the earlier result for auditability.


## 10. Append-only engineering update — 2026-11-17

- **Starting PR code commit:** `b700210ed758a19c74ebbbd63867f986ef74a129`
- **Files changed on PR branch:**
  - `tools/mt5_xauusd_historical_tick_probe.py`
  - `tests/test_mt5_xauusd_historical_tick_probe.py`
- **What changed:** Replaced the original historical request loop with fixed one-minute UTC millisecond windows; normalized tick access for MT5 structured records and test doubles; added finite-value, bid/ask, volume, timestamp-range and chronological-order validation; removed partial output on failure; writes CSV with actual newline delimiters; reuses the collector's `audit_ticks` before publishing the manifest; records the checked-out source commit, dispatcher commit and installer signer thumbprint.
- **Why:** The original code used an unsafe short-batch termination condition, had literal backslash-n output, and did not prove chunk-by-chunk integrity. A failed or incomplete response must not produce a PASS artifact.
- **Tests added:** UTC offset handling, non-overlapping chunks, inclusive final endpoint, duplicate removal, SHA-256, CSV/manifest newline integrity, invalid values, out-of-range records, non-monotonic provider response, non-DEMO rejection, empty data and broker API errors.
- **Manual trigger change on `main`:** Added `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` (dispatcher commits `89fef6def381f564180644871403d0d65dbd86a3`, `35103dd0d651417f265aaa1c326f0fe6d8964626`, `2744af30fbe105789639b1087748ef90f84cb5a7`, and `bb7c97fe66c7f6f44e4a9d38d07f3080662db9c1`). It checks out only the fixed Phase 8 branch and runs focused pytest preflight before MT5 installation and credential use.
- **Result:** Code and workflow changes committed. Automated test result is **NOT YET RUN / NOT VERIFIED**; GitHub currently reports no check runs for the latest PR code commit.
- **Remaining risks:** Actual Exness historical API behavior, historical/live source parity, signer-thumbprint independent pinning, and all research/statistical release gates remain outstanding. No historical probe has been executed.
- **Next action:** Verify the focused preflight through GitHub Actions, correct any failures, then provide the manual dispatcher link and exact validation_05 overlap interval.


### 2026-11-17 — Historical probe preflight passed; manual dispatch enabled

- **PR code commit tested:** `91e765fa8b57460154e04230fd73e4225b0a2e8f`.
- **GitHub Actions run:** [44130806654](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44130806654).
- **Result:** PASS — 268 tests passed in 2.28 seconds; Python compilation and Linux shell syntax checks passed.
- **Workflow:** the default-branch manual dispatcher is present at [xauusd-historical-tick-probe-dispatch.yml](https://github.com/Nexora-Apparel/mt5-scalping-engine/blob/main/.github/workflows/xauusd-historical-tick-probe-dispatch.yml). It checks out the fixed Phase 8 branch, records the checked-out commit, runs focused historical-probe tests first, and only proceeds to MT5 installation and the historical API call if those tests pass.
- **Manual comparison interval:** `2026-11-17T13:50:00.282Z` through `2026-11-17T14:20:02.314Z`, matching the millisecond precision of the preserved `validation_05` live capture.
- **Not yet done:** no historical probe run has been dispatched; no historical artifact or source-parity result exists.
- **Remaining trust note:** installer Authenticode validity, MetaQuotes Ltd. publisher and Code Signing EKU are checked. Independent signer-thumbprint pinning against Exness-controlled evidence remains an outstanding assurance item; the observed thumbprint is recorded in the eventual probe manifest.
- **Next action:** owner manually dispatches the workflow using the exact interval above; inspect the resulting job and artifact before any historical dataset is admitted to research.


### 2026-11-17 — First Exness historical tick probe failed at interval validation

- **Workflow run:** [44133084809](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44133084809)
- **Job:** [134215186521](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44133084809/job/134215186521)
- **Checked-out source commit:** `78611a2853237f6893266a8693a602eba816ef31`.
- **Requested interval:** `2026-11-17T13:50:00.282Z` through `2026-11-17T14:20:02.314Z`.
- **Completed successfully:** credentials/input validation, focused preflight (10 passed), MT5 installer Authenticode/publisher/EKU checks, pinned MetaTrader5 package installation, and terminal shutdown.
- **Failed step:** historical retrieval exited with `historical API returned a tick outside the requested UTC interval`.
- **Artifact:** none; the probe correctly removed partial output and did not publish a success manifest.
- **Interpretation:** MT5 returned at least one tick whose millisecond timestamp did not satisfy the exact requested interval. The original error omitted the offending timestamp and offset, so the failure does not yet distinguish sub-second/range-boundary behavior from a larger timestamp/timezone discrepancy. Historical availability and source parity remain unproven.
- **Corrective change:** improved the probe error to report the offending tick's UTC timestamp, epoch milliseconds, offsets from both requested bounds, and the exact requested interval. Added a regression assertion for those diagnostic fields.
- **Code changes:** probe commit `db24dc3c9435114bccaecb4770c91e1cbc1840bd`; test commit `0ce513664d2a663f33818802b6efa6f725cbdc42`. The combined PR branch should be rechecked for the resulting latest HEAD and CI.
- **Result:** FAIL — runtime historical request; preflight and terminal setup passed. No dataset accepted.
- **Next action:** run CI on the corrected PR HEAD, then repeat the same 30-minute overlap request. Use the new timestamp diagnostic to identify the MT5 boundary/time conversion behavior before changing interval handling. Do not widen the accepted data window or silently discard out-of-range ticks.


### 2026-11-17 — Boundary diagnostics committed and full CI revalidated

- **Corrective probe commit:** `db24dc3c9435114bccaecb4770c91e1cbc1840bd`.
- **Regression-test commit:** `0ce513664d2a663f33818802b6efa6f725cbdc42`.
- **What changed:** Out-of-range tick failures now report the offending UTC timestamp and epoch milliseconds, signed millisecond offsets from both requested bounds, and the exact requested interval. The regression test asserts all diagnostic fields are present.
- **Why:** The first runtime attempt checked out `78611a2853237f6893266a8693a602eba816ef31`, which predates the diagnostic correction. Its log therefore contains only the generic error. A second request must run the corrected branch revision to identify the actual MT5 response behavior.
- **CI:** [Run 44134469699](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44134469699), job `134220125926`, associated with test commit `0ce513664d2a663f33818802b6efa6f725cbdc42`.
- **Result:** PASS — full repository suite `268 passed in 2.36s`; Python compilation and Linux bootstrap shell syntax checks passed. This is code/CI validation only, not MT5 historical runtime validation.
- **Historical probe status:** Still FAIL on the first runtime attempt; no CSV, manifest, or accepted historical data exists. No conclusion about Exness historical coverage can yet be drawn.
- **Next action:** Manually dispatch the default-branch workflow again using the same exact overlap interval. Confirm the run checks out a commit containing `db24dc3` and `0ce5136`; then inspect the detailed offending-tick diagnostic before making any further code change.
- **Safety and release status:** XAUUSD-only, verified Exness DEMO, read-only; no orders or position management. PR #61 remains open/draft/unmerged. No widening of the accepted range, no historical backfill expansion, no holdout access, and no strategy approval.


### 2026-11-17 — Second historical probe isolated MT5 range-boundary spill

- **Workflow run:** [44137204291](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44137204291)
- **Job:** [134229887785](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44137204291/job/134229887785)
- **Checked-out source:** `178a5e7dc3e6775408ef754d8bceab6b4ab35854`.
- **Exact diagnostic:** MT5 returned tick `2026-11-17T13:50:00.137Z`, 145 ms before the requested start `13:50:00.282Z`; it was 60,144 ms before the first chunk end. This is a small range-boundary spill, not evidence of a timezone shift or a tick from a different minute/day.
- **Root cause:** The probe passed the exact requested millisecond boundaries directly to MT5 `copy_ticks_range` and treated any adjacent boundary record as fatal. MT5's range response can include a nearby tick outside the exact boundary. Strict validation was applied at the wrong layer: the API query boundary and the final dataset acceptance boundary must be distinct.
- **Corrective implementation:** Query each logical one-minute chunk with a bounded 2,000 ms guard band on both sides; validate all returned tick fields and provider ordering within that padded query; then retain only records whose `time_msc` falls inside that chunk's exact inclusive millisecond interval. Guard-band records are counted in chunk diagnostics and excluded from the CSV. The final dataset remains strictly within the user-requested overall interval. The manifest records padding and exact filtering semantics. The 2-second guard is bounded; records outside it still fail closed.
- **Regression tests added:** A realistic -145 ms leading spill and +120 ms trailing spill are excluded while the exact in-range tick is retained; a tick beyond the 2-second guard fails closed. Existing chunk, ordering, duplicate, integrity and DEMO/read-only tests remain.
- **Code commit:** `32ac493fdc726950576b9e17c1e5646c152c6dc9`.
- **Test commit:** `dd51a7a537cd3693c36a2346e98f34556ee8b9d0`.
- **CI/runtime status:** The patch is committed but the new test revision has not yet been observed passing in GitHub Actions. No historical CSV or manifest was produced by run 44137204291. The boundary-padding fix is an evidence-based correction, not yet proven against a subsequent Exness runtime request.
- **Next action:** Run full CI on the updated branch, then repeat the same 30-minute overlap request. Verify the run checked out this patch, inspect manifest filtering counters, and compare accepted historical ticks with the live capture. Do not expand to multi-day backfill until this exact overlap test and source-parity audit pass.
- **Safety/release:** XAUUSD-only; authenticated DEMO; read-only; no order or position-management calls. PR #61 remains open/draft/unmerged; holdout remains sealed; no strategy approval.
